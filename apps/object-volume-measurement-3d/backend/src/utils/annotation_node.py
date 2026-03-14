import depthai as dai
from depthai_nodes import ImgDetectionsExtended
from depthai_nodes.utils import AnnotationHelper
from typing import Dict, Tuple, Optional
import numpy as np
import cv2
import json

Point = Tuple[float, float]


class AnnotationNode(dai.node.ThreadedHostNode):
    """Interactive annotation / selection node

    Inputs:
      - in_detections: ImgDetectionsExtended produced by NN parser
      - in_rgb_stream: RGB ImgFrame
      - in_depth_stream: depth ImgFrame (will be masked to create segmented PCL)

    Outputs:
      - out_ann: filtered detections (optionally only the clicked instance)
      - out_segm: rgb frame for RGBD node
      - out_segm_depth: masked depth (background set to 0) for RGBD node
      - out_selection: Holds measuring mode value; 1 - object selected; 0 - no selection
    """

    MODE_NOSELECTION = 0
    MODE_MEASURE = 1
    MODE_PLANE_CAPTURE = 2

    def __init__(self, label_encoding: Dict[int, str] = {}) -> None:
        dai.node.ThreadedHostNode.__init__(self)

        self.in_detections = self.createInput()
        self.in_rgb_stream = self.createInput()
        self.in_depth_stream = self.createInput()
        self.in_meas_result = self.createInput()

        self.out_segm = self.createOutput()
        self.out_segm_depth = self.createOutput()
        self.out_selection = self.createOutput()
        self.out_ann = self.createOutput()

        self._label_encoding = label_encoding

        self._selection_point: Optional[Tuple[float, float]] = None  # normalized coords
        self._keep_top_only: bool = True

        self._src_trans = None
        self._dst_trans = None

        self._plane_capture: bool = False

        self._last_dims = None
        self._last_vol = None

    def setLabelEncoding(self, label_encoding: Dict[int, str]) -> None:
        """Sets the label encoding.

        @param label_encoding: The label encoding with labels as keys and label names as
            values.
        @type label_encoding: Dict[int, str]
        """
        if not isinstance(label_encoding, Dict):
            raise ValueError("label_encoding must be a dictionary.")
        self._label_encoding = label_encoding

    def setSelectionPoint(self, nx: float, ny: float) -> None:
        nx = float(max(0.0, min(1.0, nx)))
        ny = float(max(0.0, min(1.0, ny)))
        self._selection_point = (nx, ny)

    def clearSelection(self) -> None:
        self._selection_point = None
        print("Selection cleared.")

    def setKeepTopOnly(self, keep_top: bool) -> None:
        """If True, keep only the highest-confidence detection under the click."""
        self._keep_top_only = bool(keep_top)

    def requestPlaneCapture(self, enable: bool = True) -> None:
        """Ask the node to emit exactly one cycle with FULL depth (mode=2)."""
        self._plane_capture = bool(enable)

    def clearCachedMeasurements(self):
        self._last_dims = None
        self._last_vol = None

        while True:
            if not self.in_meas_result.tryGet():
                break

    def build(
        self,
        detections: dai.Node.Output,
        rgb_stream: Optional[dai.Node.Output] = None,
        depth_stream: Optional[dai.Node.Output] = None,
        label_encoding: Optional[Dict[int, str]] = None,
    ) -> "AnnotationNode":
        if label_encoding is not None:
            self.setLabelEncoding(label_encoding)

        detections.link(self.in_detections)

        if rgb_stream is not None:
            rgb_stream.link(self.in_rgb_stream)

        if depth_stream is not None:
            depth_stream.link(self.in_depth_stream)

        return self

    def _send_mode(self, mode: int, src_msg: dai.ImgFrame) -> None:
        b = dai.Buffer()
        b.setData(bytes([mode & 0xFF]))
        b.setTimestamp(src_msg.getTimestamp())
        b.setSequenceNum(src_msg.getSequenceNum())
        self.out_selection.send(b)

    def point_in_convex_quad(
        self, px: float, py: float, corners, eps: float = 1e-9
    ) -> bool:
        """
        corners: list[(x,y)]
        Returns True if (px, py) lies inside/on a convex quad defined by 'corners'.
        """

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        s = []
        for i in range(4):
            o = corners[i]
            a = corners[(i + 1) % 4]
            s.append(cross(o, a, (px, py)))

        return all(v >= -eps for v in s) or all(v <= eps for v in s)

    def _contains_point(self, det, sx_rgb, sy_rgb) -> bool:
        # corners are NN-normalized → warp to RGB-normalized
        rr = det.rotated_rect
        pts_nn_norm = [(p.x, p.y) for p in rr.getPoints()]
        pts_rgb_norm = self._nn_to_rgb_norm_pts(pts_nn_norm)
        return self.point_in_convex_quad(sx_rgb, sy_rgb, pts_rgb_norm)

    def _prepare_mask_transform(
        self, src_T: dai.ImgTransformation, dst_T: dai.ImgTransformation
    ):
        """Precompute homography to warp NN-space masks into RGB-space.

        Args:
          src_T: ImgTransformation for the NN input space (sensor→NN)
          dst_T: ImgTransformation for the RGB image space (sensor→RGB)
        """
        A = np.array(src_T.getMatrix(), dtype=np.float32)
        B = np.array(dst_T.getMatrix(), dtype=np.float32)

        # NN -> RGB
        try:
            self._H_nn_to_rgb = B @ np.linalg.inv(A)
        except np.linalg.LinAlgError:
            self._H_nn_to_rgb = B @ np.linalg.pinv(A)

        dw, dh = dst_T.getSize()
        self._dst_size = (int(dw), int(dh))

    def _mask_nn_to_rgb(self, mask_src_2d: np.ndarray) -> np.ndarray:
        """
        Warp a NN-space mask to RGB-space using the precomputed homography.
        """
        dst_w, dst_h = self._dst_size

        mask = mask_src_2d
        if mask.dtype not in (np.int16, np.float32, np.uint8, np.uint16):
            mask = mask.astype(np.int16, copy=False)

        return cv2.warpPerspective(
            mask,
            self._H_nn_to_rgb,
            (dst_w, dst_h),
            flags=cv2.INTER_NEAREST,
            borderValue=-1,
        )

    # ---- drawing (NN-normalized coords for AnnotationHelper) ----
    def _draw_mask(self, helper: AnnotationHelper, mask: np.ndarray, idx: int):
        h, w = mask.shape
        binary = (mask == idx).astype(np.uint8)
        if not np.any(binary):
            return
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            epsilon = 0.01 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            pts = approx.reshape(-1, 2)
            # NN-normalized points
            pts_norm = [(float(x) / w, float(y) / h) for x, y in pts]
            self._warp_polygon_and_draw(
                helper,
                pts_norm,
                outline_color=(1.0, 0.5, 1.0, 0.0),
                fill_color=(1.0, 0.5, 1.0, 0.4),
                thickness=1,
            )

    def _draw_rotrect_and_label(self, helper: AnnotationHelper, det, text: str):
        # rr corners are NN-normalized already (0..1 in NN space)
        rr = det.rotated_rect
        corners = rr.getPoints()
        pts_nn_norm = [(p.x, p.y) for p in corners]
        # draw polygon in RGB space
        self._warp_polygon_and_draw(
            helper,
            pts_nn_norm,
            outline_color=(1.0, 0.5, 1.0, 1.0),
            fill_color=None,
            thickness=2,
        )
        # label at first corner (warp a single point)
        lbl_xy = self._nn_to_rgb_norm_pts([(pts_nn_norm[0][0], pts_nn_norm[0][1])])[0]
        helper.draw_text(
            text,
            lbl_xy,
            color=(0.5, 0.15, 1.0, 1.0),
            background_color=(1.0, 1.0, 0.0, 0.8),
            size=19,
        )

    def _nn_to_rgb_norm_pts(self, pts_norm):
        """
        pts_norm: list of (u,v) normalized to NN input (0..1)
        returns: list of (U,V) normalized to RGB frame (0..1)
        """
        # sizes
        sw, sh = self._src_trans.getSize()
        dw, dh = self._dst_size

        # to NN pixels
        P = np.array([[u * sw, v * sh, 1.0] for (u, v) in pts_norm], dtype=np.float32).T
        # homography NN->RGB
        Q = self._H_nn_to_rgb @ P
        Q /= Q[2:3, :] + 1e-12
        # to RGB-normalized
        U = (Q[0, :] / float(dw)).clip(0, 1)
        V = (Q[1, :] / float(dh)).clip(0, 1)
        return list(zip(U.tolist(), V.tolist()))

    def _warp_polygon_and_draw(self, helper, pts_nn_norm, **poly_kwargs):
        pts_rgb_norm = self._nn_to_rgb_norm_pts(pts_nn_norm)
        helper.draw_polyline(pts_rgb_norm, closed=True, **poly_kwargs)

    def _clear_dets_and_mask(self, det) -> None:
        """
        Clears detections and masks
        """
        det.detections = []
        m = getattr(det, "masks", None)
        if m is not None and getattr(m, "size", 0):
            # -1 - background
            det.masks = np.full_like(m, -1)

    def _poll_measurement_result(self):
        buf = self.in_meas_result.tryGet()
        if not buf:
            return
        try:
            data = bytes(buf.getData()).decode("utf-8")
            j = json.loads(data)
            self._last_dims = j.get("dims", None)
            self._last_vol = j.get("vol", None)
        except Exception as e:
            print("AnnotationNode: bad meas payload:", e)

    def run(self) -> None:
        while self.isRunning():
            det_msg = self.in_detections.get()
            img_msg = self.in_rgb_stream.get()
            depth_msg = self.in_depth_stream.get()

            depth_map = depth_msg.getFrame()
            rgb = img_msg.getCvFrame()

            helper = AnnotationHelper()

            H, W = rgb.shape[:2]

            # Note: for temp sync of pcl and MODE messages in measurement node (to do)
            rgbF = dai.ImgFrame()
            rgbF.setType(img_msg.getType())
            rgbF.setWidth(W)
            rgbF.setHeight(H)
            rgbF.setData(img_msg.getData())
            rgbF.setTimestamp(depth_msg.getTimestamp())
            rgbF.setSequenceNum(depth_msg.getSequenceNum())
            rgbF.setTransformation(img_msg.getTransformation())

            if self._src_trans is None or self._dst_trans is None:
                self._src_trans = det_msg.getTransformation()
                self._dst_trans = img_msg.getTransformation()
                self._prepare_mask_transform(
                    self._src_trans, self._dst_trans
                )  # To transform mask from NN space to rgb space

            assert isinstance(det_msg, ImgDetectionsExtended)
            for detection in det_msg.detections:
                detection.label_name = self._label_encoding.get(
                    detection.label, "unknown"
                )

            # Plane capture when switch to heightgrid
            if self._plane_capture:
                # self._send_mode(self.MODE_MEASURE, depth_msg)
                self._send_mode(self.MODE_PLANE_CAPTURE, depth_msg)
                self.out_ann.send(
                    AnnotationHelper().build(
                        img_msg.getTimestamp(), img_msg.getSequenceNum()
                    )
                )
                self.out_segm.send(rgbF)
                self.out_segm_depth.send(depth_msg)  # full-scene depth
                # self._send_mode(self.MODE_MEASURE, img_msg)
                # self._plane_capture = False
                continue

            m = det_msg.masks
            dets = det_msg.detections
            mask_rgb = None

            # no click show everything
            if self._selection_point is None:
                # draw masks + boxes + labels for ALL detections
                if m is not None and m.size:
                    # assume instance id == detection index (as produced by parser)
                    present_ids = set(int(v) for v in np.unique(m) if v >= 0)
                    for idx in present_ids:
                        self._draw_mask(helper, m, idx)
                for d in dets:
                    label_txt = f"{d.label_name} {getattr(d, 'confidence', 0.0):.2f}"
                    self._draw_rotrect_and_label(helper, d, label_txt)

                # emit: annotations + full depth + all dets
                ann_msg = helper.build(img_msg.getTimestamp(), img_msg.getSequenceNum())
                self._send_mode(self.MODE_NOSELECTION, depth_msg)
                self.out_ann.send(ann_msg)
                self.out_segm.send(rgbF)
                self.out_segm_depth.send(depth_msg)
                continue

            # with a click keep only the instance under the click
            sx, sy = self._selection_point
            kept_idx = [
                i for i, d in enumerate(dets) if self._contains_point(d, sx, sy)
            ]
            if self._keep_top_only and kept_idx:
                kept_idx = [
                    max(kept_idx, key=lambda i: getattr(dets[i], "confidence", 0.0))
                ]

            if not kept_idx:
                # click hit nothing behave like no selection (signal NOSELECTION)
                if m is not None and m.size:
                    present_ids = set(int(v) for v in np.unique(m) if v >= 0)
                    for idx in present_ids:
                        self._draw_mask(helper, m, idx)
                for d in dets:
                    label_txt = f"{d.label_name} {getattr(d, 'confidence', 0.0):.2f}"
                    self._draw_rotrect_and_label(helper, d, label_txt)

                ann_msg = helper.build(img_msg.getTimestamp(), img_msg.getSequenceNum())
                self._send_mode(self.MODE_NOSELECTION, depth_msg)
                self.out_ann.send(ann_msg)
                self.out_segm.send(rgbF)
                self.out_segm_depth.send(depth_msg)

                self.clearSelection()
                self.clearCachedMeasurements()

                continue

            # transform mask NN space -> RGB space
            if m is not None:
                mask_rgb = self._mask_nn_to_rgb(m)

            # keep only the chosen detection
            sel_i = kept_idx[0]
            selected_mid = -1

            # pick the mask instance id under the click
            if mask_rgb is not None and mask_rgb.size:
                h_mask, w_mask = mask_rgb.shape[:2]
                px = int(np.clip(sx * w_mask, 0, w_mask - 1))
                py = int(np.clip(sy * h_mask, 0, h_mask - 1))
                selected_mid = (
                    int(mask_rgb[py, px])
                    if mask_rgb is not None and mask_rgb.size
                    else -1
                )

            if m is not None and selected_mid != -1:
                # draw the masks of every detection, measurements only for the selected one
                present_ids = set(int(v) for v in np.unique(m) if v >= 0)
                for idx in present_ids:
                    self._draw_mask(helper, m, idx)

                self._poll_measurement_result()

                for i, d in enumerate(dets):
                    if i == sel_i:
                        base = f"{d.label_name} {getattr(d, 'confidence', 0.0):.2f}"
                        extra = ""
                        if (
                            isinstance(self._last_dims, list)
                            and len(self._last_dims) == 3
                        ):
                            extra += f"\n{self._last_dims[0]:.1f} × {self._last_dims[1]:.1f} × {self._last_dims[2]:.1f} cm"
                        if isinstance(self._last_vol, (int, float)):
                            extra += f"\n{int(np.rint(float(self._last_vol)))} cm³"
                        label_txt = base + extra
                        self._draw_rotrect_and_label(helper, d, label_txt)
                        continue
                    base = f"{d.label_name} {getattr(d, 'confidence', 0.0):.2f}"
                    self._draw_rotrect_and_label(helper, d, base)

                # Mask depth to get segmented pointcloud
                keep = mask_rgb == selected_mid
                depth_u16 = np.ascontiguousarray(depth_map, dtype=np.uint16)
                depth_u16[~keep] = 0

                depthF = dai.ImgFrame()
                depthF.setType(dai.ImgFrame.Type.RAW16)
                depthF.setWidth(W)
                depthF.setHeight(H)
                depthF.setData(depth_u16.tobytes())
                depthF.setTimestamp(depth_msg.getTimestamp())
                depthF.setSequenceNum(depth_msg.getSequenceNum())
                depthF.setTransformation(depth_msg.getTransformation())

                ann_msg = helper.build(img_msg.getTimestamp(), img_msg.getSequenceNum())
                self._send_mode(self.MODE_MEASURE, depthF)
                self.out_ann.send(ann_msg)
                self.out_segm.send(rgbF)
                self.out_segm_depth.send(depthF)
                continue

            # No valid instance under click - show all (signal NOSELECTION)
            if m is not None and m.size:
                present_ids = set(int(v) for v in np.unique(m) if v >= 0)
                for idx in present_ids:
                    self._draw_mask(helper, m, idx)
            for d in dets:
                label_txt = f"{d.label_name} {getattr(d, 'confidence', 0.0):.2f}"
                self._draw_rotrect_and_label(helper, d, label_txt)

            ann_msg = helper.build(img_msg.getTimestamp(), img_msg.getSequenceNum())
            self._send_mode(self.MODE_NOSELECTION, depth_msg)
            self.out_ann.send(ann_msg)
            self.out_segm.send(rgbF)
            self.out_segm_depth.send(depth_msg)
