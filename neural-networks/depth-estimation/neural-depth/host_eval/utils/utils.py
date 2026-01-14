import os
import cv2
import numpy as np


class PFMReader:
    @staticmethod
    def read(file_path):
        with open(file_path, "rb") as file:
            header_lines = []

            while len(header_lines) < 3:
                line = file.readline().decode("latin-1").strip()
                if not line or line.startswith("#"):
                    continue
                header_lines.append(line)

            color_type = header_lines[0]
            if color_type not in ["PF", "Pf"]:
                raise ValueError(f"Invalid PFM header: Unknown type '{color_type}'")

            channels = 3 if color_type == "PF" else 1

            dims = header_lines[1].split()
            width, height = int(dims[0]), int(dims[1])

            scale = float(header_lines[2])
            endian = "<" if scale < 0 else ">"
            scale_factor = abs(scale)

            data = np.fromfile(file, dtype=f"{endian}f")

            if channels == 3:
                shape = (height, width, 3)
            else:
                shape = (height, width)

            try:
                data = np.reshape(data, shape)
            except ValueError:
                raise ValueError(
                    "PFM data mismatch: Header says "
                    f"{width}x{height}x{channels}, but found {data.size} floats."
                )

            data = np.flipud(data)
            data[data == np.inf] = 0
            data[data < 0] = 0
            return data.astype(np.float32)

    @staticmethod
    def write(file_path, image, scale=1):
        image = image.astype(np.float32)

        if len(image.shape) == 3 and image.shape[2] == 3:
            color = True
            dtype = "PF"
        else:
            color = False
            dtype = "Pf"

        image = np.flipud(image)

        height, width = image.shape[:2]

        scale_str = f"{-scale}"

        with open(file_path, "wb") as file:
            header = f"{dtype}\n{width} {height}\n{scale_str}\n"
            file.write(header.encode("latin-1"))
            image.tofile(file)


class StereoDataSample:
    PAD_TOP_RIGHT = "top_right"
    PAD_CENTER = "center"

    def __init__(
        self,
        left_path,
        right_path,
        eval_size,
        inference_size,
        gt_path=None,
        to_gray=False,
        max_disparity=192.0,
        padding_mode="top_right",
        border_erase_pixels=0,
        debug=False,
        is_legacy_logic=False,
    ):
        self.left_path = left_path
        self.right_path = right_path
        self.gt_path = gt_path
        self.eval_size = eval_size
        self.inference_size = inference_size
        self.to_gray = to_gray
        self.max_disparity = max_disparity
        self.padding_mode = padding_mode
        self.border_erase_pixels = border_erase_pixels
        self.debug = debug
        self.is_legacy_logic = is_legacy_logic

        if padding_mode not in [self.PAD_TOP_RIGHT, self.PAD_CENTER]:
            raise ValueError(
                f"Invalid padding_mode: {padding_mode}. Must be "
                f"'{self.PAD_TOP_RIGHT}' or '{self.PAD_CENTER}'"
            )

        self.original_left = self._load_image(left_path, is_gt=False)
        self.original_right = self._load_image(right_path, is_gt=False)
        self.original_gt = self._load_image(gt_path, is_gt=True) if gt_path else None

        self.original_size = self.original_left.shape[:2]

        self.input_left = None
        self.input_right = None
        self.processed_gt = None

        self._eval_disparity = None
        self._eval_confidence = None
        self._eval_edge = None

        self.meta_step1 = {}
        self.meta_step2 = {}

        self._preprocess(debug=debug)

    def _preprocess(self, debug=False):
        left_bgr_u8 = self.original_left.astype(np.uint8)
        right_bgr_u8 = self.original_right.astype(np.uint8)

        left_rgb_u8 = cv2.cvtColor(left_bgr_u8, cv2.COLOR_BGR2RGB)
        right_rgb_u8 = cv2.cvtColor(right_bgr_u8, cv2.COLOR_BGR2RGB)

        left_rgb_u8_f32 = left_rgb_u8.astype(np.float32)
        right_rgb_u8_f32 = right_rgb_u8.astype(np.float32)

        l_eval, meta1 = self._resize_pad_safe(left_rgb_u8_f32, self.eval_size)
        r_eval, _ = self._resize_pad_safe(right_rgb_u8_f32, self.eval_size)

        l_eval_u8 = l_eval.astype(np.uint8)
        r_eval_u8 = r_eval.astype(np.uint8)

        self.meta_step1 = meta1

        if debug:
            print(f"[DEBUG _preprocess] After resize to eval: shape={l_eval_u8.shape}")

        if self.original_gt is not None:
            if debug:
                print(f"[DEBUG _preprocess] original_gt shape={self.original_gt.shape}")
            gt_eval, _ = self._resize_pad_safe(
                self.original_gt, self.eval_size, is_disparity=True
            )
            self.processed_gt = gt_eval
            if debug:
                print(f"[DEBUG _preprocess] processed_gt shape={gt_eval.shape}")

        l_inf_u8_f32 = l_eval_u8.astype(np.float32)
        r_inf_u8_f32 = r_eval_u8.astype(np.float32)

        l_inf_resized, meta2 = self._resize_pad_safe(l_inf_u8_f32, self.inference_size)
        r_inf_resized, _ = self._resize_pad_safe(r_inf_u8_f32, self.inference_size)

        l_inf_u8 = l_inf_resized.astype(np.uint8)
        r_inf_u8 = r_inf_resized.astype(np.uint8)

        if debug:
            print(
                f"[DEBUG _preprocess] After resize to inference: shape={l_inf_u8.shape}"
            )

        if l_inf_u8.shape[2] == 3:
            l_gray_u8 = cv2.cvtColor(l_inf_u8, cv2.COLOR_RGB2GRAY)
            r_gray_u8 = cv2.cvtColor(r_inf_u8, cv2.COLOR_RGB2GRAY)
        else:
            l_gray_u8 = l_inf_u8.squeeze()
            r_gray_u8 = r_inf_u8.squeeze()

        l_gray_u8 = np.expand_dims(l_gray_u8, axis=2)
        r_gray_u8 = np.expand_dims(r_gray_u8, axis=2)

        l_inf = l_gray_u8.astype(np.float32)
        r_inf = r_gray_u8.astype(np.float32)

        self.meta_step2 = meta2
        self.input_left = l_inf
        self.input_right = r_inf

    @staticmethod
    def _border_erase(disp, border_pixels):
        if border_pixels <= 0:
            return disp
        disp = disp.copy()
        disp[:border_pixels, :] = 0
        disp[disp.shape[0] - border_pixels :, :] = 0
        disp[:, :border_pixels] = 0
        disp[:, disp.shape[1] - border_pixels :] = 0
        return disp

    def get_inference_inputs(self):
        return self.input_left, self.input_right

    def get_eval_images(self, strip_padding=False):
        l_img = self._ensure_color_format(self.original_left, self.to_gray)
        r_img = self._ensure_color_format(self.original_right, self.to_gray)

        l_eval, _ = self._resize_pad_safe(l_img, self.eval_size)
        r_eval, _ = self._resize_pad_safe(r_img, self.eval_size)

        if strip_padding:
            pad_top = self.meta_step1["pad_top"]
            pad_bottom = self.meta_step1["pad_bottom"]
            pad_left = self.meta_step1["pad_left"]
            pad_right = self.meta_step1["pad_right"]

            h_end = (
                self.eval_size[0] - pad_bottom if pad_bottom > 0 else self.eval_size[0]
            )
            w_end = (
                self.eval_size[1] - pad_right if pad_right > 0 else self.eval_size[1]
            )

            return (
                l_eval[pad_top:h_end, pad_left:w_end],
                r_eval[pad_top:h_end, pad_left:w_end],
            )

        return l_eval, r_eval

    def get_ground_truth(self, target="eval", strip_padding=False):
        if self.original_gt is None:
            return None

        if target == "eval":
            if strip_padding:
                pad_top = self.meta_step1["pad_top"]
                pad_bottom = self.meta_step1["pad_bottom"]
                pad_left = self.meta_step1["pad_left"]
                pad_right = self.meta_step1["pad_right"]

                h_end = (
                    self.eval_size[0] - pad_bottom
                    if pad_bottom > 0
                    else self.eval_size[0]
                )
                w_end = (
                    self.eval_size[1] - pad_right
                    if pad_right > 0
                    else self.eval_size[1]
                )

                return self.processed_gt[pad_top:h_end, pad_left:w_end]
            return self.processed_gt
        if target == "original":
            return self.original_gt
        raise ValueError(f"Unknown target: {target}")

    def set_predictions(
        self, disparity, confidence, edge, conf_threshold, edge_threshold, debug=False
    ):
        pad_top = self.meta_step2["pad_top"]
        pad_bottom = self.meta_step2["pad_bottom"]
        pad_left = self.meta_step2["pad_left"]
        pad_right = self.meta_step2["pad_right"]

        h_end = (
            self.inference_size[0] - pad_bottom
            if pad_bottom > 0
            else self.inference_size[0]
        )
        w_end = (
            self.inference_size[1] - pad_right
            if pad_right > 0
            else self.inference_size[1]
        )

        if debug:
            print(
                f"[DEBUG set_predictions] inference_size={self.inference_size}, "
                f"eval_size={self.eval_size}"
            )
            print(f"[DEBUG set_predictions] meta_step2={self.meta_step2}")
            print(
                "[DEBUG set_predictions] crop region: "
                f"[{pad_top}:{h_end}, {pad_left}:{w_end}]"
            )
            print(
                "[DEBUG set_predictions] disparity input shape="
                f"{disparity.shape}, range=[{disparity.min():.3f}, "
                f"{disparity.max():.3f}]"
            )

        disp = np.squeeze(disparity)
        cropped = disp[pad_top:h_end, pad_left:w_end]
        cropped_w = cropped.shape[1]

        if debug:
            print(
                f"[DEBUG set_predictions] cropped shape={cropped.shape}, "
                f"cropped_w={cropped_w}"
            )
            print(
                "[DEBUG set_predictions] disp scale factor = "
                f"{self.eval_size[1]} / {cropped_w} = "
                f"{self.eval_size[1] / cropped_w:.6f}"
            )

        disp_eval = cv2.resize(
            cropped,
            (self.eval_size[1], self.eval_size[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        disp_eval = disp_eval * (self.eval_size[1] / cropped_w)

        if debug:
            print(
                "[DEBUG set_predictions] disp_eval BEFORE filtering: "
                f"range=[{disp_eval.min():.3f}, {disp_eval.max():.3f}]"
            )

        conf = np.squeeze(confidence)
        cropped = conf[pad_top:h_end, pad_left:w_end]
        conf_eval = cv2.resize(
            cropped,
            (self.eval_size[1], self.eval_size[0]),
            interpolation=cv2.INTER_LINEAR,
        )

        edg = np.squeeze(edge)
        cropped = edg[pad_top:h_end, pad_left:w_end]
        edge_eval = cv2.resize(
            cropped,
            (self.eval_size[1], self.eval_size[0]),
            interpolation=cv2.INTER_LINEAR,
        )

        disp_eval[conf_eval < conf_threshold] = 0.0
        disp_eval = disp_eval * (edge_eval < edge_threshold).astype(np.float32)

        self._eval_disparity = disp_eval
        self._eval_confidence = conf_eval
        self._eval_edge = edge_eval

    def get_predictions(self, target="eval", strip_padding=False):
        if self._eval_disparity is None:
            raise ValueError("No predictions set yet.")

        if target == "eval":
            if strip_padding:
                pad_top = self.meta_step1["pad_top"]
                pad_bottom = self.meta_step1["pad_bottom"]
                pad_left = self.meta_step1["pad_left"]
                pad_right = self.meta_step1["pad_right"]

                h_end = (
                    self.eval_size[0] - pad_bottom
                    if pad_bottom > 0
                    else self.eval_size[0]
                )
                w_end = (
                    self.eval_size[1] - pad_right
                    if pad_right > 0
                    else self.eval_size[1]
                )

                disp = self._eval_disparity[pad_top:h_end, pad_left:w_end]
                conf = self._eval_confidence[pad_top:h_end, pad_left:w_end]
                edge = self._eval_edge[pad_top:h_end, pad_left:w_end]

                if self.border_erase_pixels > 0:
                    disp = self._border_erase(disp, self.border_erase_pixels)

                return disp, conf, edge
            return self._eval_disparity, self._eval_confidence, self._eval_edge

        if target == "original":
            pad_top = self.meta_step1["pad_top"]
            pad_bottom = self.meta_step1["pad_bottom"]
            pad_left = self.meta_step1["pad_left"]
            pad_right = self.meta_step1["pad_right"]

            h_end = (
                self.eval_size[0] - pad_bottom if pad_bottom > 0 else self.eval_size[0]
            )
            w_end = (
                self.eval_size[1] - pad_right if pad_right > 0 else self.eval_size[1]
            )

            cropped = self._eval_disparity[pad_top:h_end, pad_left:w_end]
            cropped_w = cropped.shape[1]
            final_disparity = cv2.resize(
                cropped,
                (self.original_size[1], self.original_size[0]),
                interpolation=cv2.INTER_LINEAR,
            )
            final_disparity = final_disparity * (self.original_size[1] / cropped_w)

            cropped = self._eval_confidence[pad_top:h_end, pad_left:w_end]
            final_confidence = cv2.resize(
                cropped,
                (self.original_size[1], self.original_size[0]),
                interpolation=cv2.INTER_LINEAR,
            )

            cropped = self._eval_edge[pad_top:h_end, pad_left:w_end]
            final_edge = cv2.resize(
                cropped,
                (self.original_size[1], self.original_size[0]),
                interpolation=cv2.INTER_LINEAR,
            )

            return final_disparity, final_confidence, final_edge

        raise ValueError(f"Unknown target: {target}")

    def compute_metrics(
        self, target="eval", is_legacy_code=False, strip_padding=False, debug=False
    ):
        if self.original_gt is None:
            return {}
        if self._eval_disparity is None:
            raise ValueError("No predictions available.")

        if target == "eval":
            if strip_padding:
                pad_top = self.meta_step1["pad_top"]
                pad_bottom = self.meta_step1["pad_bottom"]
                pad_left = self.meta_step1["pad_left"]
                pad_right = self.meta_step1["pad_right"]

                h_end = (
                    self.eval_size[0] - pad_bottom
                    if pad_bottom > 0
                    else self.eval_size[0]
                )
                w_end = (
                    self.eval_size[1] - pad_right
                    if pad_right > 0
                    else self.eval_size[1]
                )

                gt = self.processed_gt[pad_top:h_end, pad_left:w_end]
                pred = self._eval_disparity[pad_top:h_end, pad_left:w_end]

                if self.border_erase_pixels > 0:
                    pred = self._border_erase(pred, self.border_erase_pixels)
                    if debug:
                        print(
                            "[DEBUG compute_metrics] Applied border_erase("
                            f"{self.border_erase_pixels}) after strip_padding"
                        )
            else:
                gt = self.processed_gt
                pred = self._eval_disparity

        elif target == "original":
            gt = self.original_gt
            pad_top = self.meta_step1["pad_top"]
            pad_bottom = self.meta_step1["pad_bottom"]
            pad_left = self.meta_step1["pad_left"]
            pad_right = self.meta_step1["pad_right"]

            h_end = (
                self.eval_size[0] - pad_bottom if pad_bottom > 0 else self.eval_size[0]
            )
            w_end = (
                self.eval_size[1] - pad_right if pad_right > 0 else self.eval_size[1]
            )

            cropped = self._eval_disparity[pad_top:h_end, pad_left:w_end]
            cropped_w = cropped.shape[1]
            pred = cv2.resize(
                cropped,
                (self.original_size[1], self.original_size[0]),
                interpolation=cv2.INTER_LINEAR,
            )
            pred = pred * (self.original_size[1] / cropped_w)

        else:
            raise ValueError(f"Unknown target: {target}")

        if debug:
            print(f"[DEBUG compute_metrics] target={target}")
            print(
                "[DEBUG compute_metrics] gt shape="
                f"{gt.shape}, range=[{gt.min():.3f}, {gt.max():.3f}]"
            )
            print(
                "[DEBUG compute_metrics] pred shape="
                f"{pred.shape}, range=[{pred.min():.3f}, {pred.max():.3f}]"
            )
            print(
                "[DEBUG compute_metrics] gt>0 count="
                f"{(gt > 0).sum()}, pred>0 count={(pred > 0).sum()}"
            )

        valid_mask = (gt > 0) & (pred > 0) & (gt <= self.max_disparity)

        if valid_mask.sum() == 0:
            return {"EPE": 0.0, "valid_pixels": 0, "density": 0.0}

        gt_valid_mask = (gt > 0) & (gt <= self.max_disparity)
        total_gt_valid = gt_valid_mask.sum()
        pred_valid_in_gt_region = (
            (pred[gt_valid_mask] > 0) & (pred[gt_valid_mask] <= self.max_disparity)
        ).sum()
        density = (
            pred_valid_in_gt_region / total_gt_valid if total_gt_valid > 0 else 0.0
        )

        error = np.abs(gt[valid_mask] - pred[valid_mask])
        epe = np.mean(error)
        d1 = (error > 3.0) | (error > 0.05 * np.abs(gt[valid_mask]))
        bad1 = error > 1.0
        bad2 = error > 2.0
        bad3 = error > 3.0
        bad4 = error > 4.0

        return {
            "EPE": float(epe),
            "D1_all": float(d1.mean()) * 100,
            "bad1": float(bad1.mean()) * 100,
            "bad2": float(bad2.mean()) * 100,
            "bad3": float(bad3.mean()) * 100,
            "bad4": float(bad4.mean()) * 100,
            "density": float(density),
        }

    def _resize_pad_safe(self, img, target_size, is_disparity=False):
        h, w = img.shape[:2]
        target_h, target_w = target_size

        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        interp = cv2.INTER_LINEAR
        resized = cv2.resize(img, (new_w, new_h), interpolation=interp)

        if is_disparity:
            resized = resized * (new_w / w)

        resized = self._restore_channels(resized, img.shape)

        if self.padding_mode == self.PAD_TOP_RIGHT:
            pad_top = target_h - new_h
            pad_bottom = 0
            pad_left = 0
            pad_right = target_w - new_w
        else:
            pad_left = (target_w - new_w) // 2
            pad_right = target_w - new_w - pad_left
            pad_top = (target_h - new_h) // 2
            pad_bottom = target_h - new_h - pad_top

        padded = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=0,
        )
        padded = self._restore_channels(padded, img.shape)

        meta = {
            "scale": scale,
            "pad_top": pad_top,
            "pad_bottom": pad_bottom,
            "pad_left": pad_left,
            "pad_right": pad_right,
            "padding_mode": self.padding_mode,
        }
        return padded, meta

    def _load_image(self, path, is_gt):
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        flags = cv2.IMREAD_UNCHANGED if is_gt else cv2.IMREAD_COLOR

        if is_gt:
            img = PFMReader.read(path)
        else:
            img = cv2.imread(path, flags)
        if img is None:
            raise ValueError(f"Failed to load {path}")
        return img.astype(np.float32)

    def _ensure_color_format(self, img, to_gray):
        if len(img.shape) == 2:
            img = img[:, :, np.newaxis]
        if to_gray and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[:, :, np.newaxis]
        elif not to_gray and img.shape[2] == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def _restore_channels(self, img, original_shape):
        if len(img.shape) == 2 and len(original_shape) == 3:
            img = img[:, :, np.newaxis]
        return img
