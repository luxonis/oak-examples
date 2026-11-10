import depthai as dai
from depthai_nodes.utils import AnnotationHelper
from depthai_nodes.node.utils.message_remapping import remap_message
from typing import Dict, Tuple, Optional
import numpy as np
import cv2
import json
from .overlay_layout import draw_label

Point = Tuple[float, float]


class AnnotationNode(dai.node.ThreadedHostNode):
    """Interactive annotation / selection node

    Inputs:
      - in_sync: synchronized RGB, aligned detections/mask, and aligned depth

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

        self.in_sync = self.createInput()
        self.in_meas_result = self.createInput()
        # This feedback is display state, and is not consumed during plane capture
        # or without a selection. Never let old results block the PCL pipeline.
        self.in_meas_result.setBlocking(False)
        self.in_meas_result.setMaxSize(1)

        self.out_segm = self.createOutput()
        self.out_segm_depth = self.createOutput()
        self.out_selection = self.createOutput()
        self.out_ann = self.createOutput()

        self._label_encoding = label_encoding

        self._selection_point: Optional[Tuple[float, float]] = None  # normalized coords
        self._keep_top_only: bool = True

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
        """Stream full depth until MeasurementNode ends or cancels capture."""
        self._plane_capture = bool(enable)

    def clearCachedMeasurements(self):
        self._last_dims = None
        self._last_vol = None

        while True:
            if not self.in_meas_result.tryGet():
                break

    def build(
        self,
        synchronized: dai.Node.Output,
        label_encoding: Optional[Dict[int, str]] = None,
    ) -> "AnnotationNode":
        if label_encoding is not None:
            self.setLabelEncoding(label_encoding)

        synchronized.link(self.in_sync)

        return self

    def _send_outputs(self, helper, rgb: dai.ImgFrame, depth: dai.ImgFrame, mode: int):
        mode_message = dai.Buffer()
        mode_message.setData(bytes([mode]))
        mode_message.setBufferMetadataFrom(rgb)
        annotations = helper.build(rgb.getTimestamp(), rgb.getSequenceNum())
        annotations.setBufferMetadataFrom(rgb)
        annotations.setTransformation(rgb.getTransformation())
        self.out_selection.send(mode_message)
        self.out_ann.send(annotations)
        self.out_segm.send(rgb)
        self.out_segm_depth.send(depth)

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
        width, height = self._dst_size
        corners = [
            (p.x / width, p.y / height)
            for p in det.getBoundingBox().denormalize(width, height).getPoints()
        ]
        return self.point_in_convex_quad(sx_rgb, sy_rgb, corners)

    # Detections and mask pixels have already been aligned to RGB by Align.
    def _draw_mask(self, helper: AnnotationHelper, mask: np.ndarray, idx: int):
        if idx == 255:  # background
            return
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
            pts_norm = [(float(x) / w, float(y) / h) for x, y in pts]
            helper.draw_polyline(
                pts_norm,
                closed=True,
                outline_color=(1.0, 0.5, 1.0, 0.0),
                fill_color=(1.0, 0.5, 1.0, 0.4),
                thickness=1,
            )

    def _draw_rotrect_and_label(self, helper: AnnotationHelper, det, text: str):
        width, height = self._dst_size
        corners = [
            (p.x / width, p.y / height)
            for p in det.getBoundingBox().denormalize(width, height).getPoints()
        ]
        helper.draw_polyline(
            corners,
            closed=True,
            outline_color=(1.0, 0.5, 1.0, 1.0),
            fill_color=None,
            thickness=2,
        )
        draw_label(
            helper,
            text,
            corners[0],
            *self._dst_size,
            color=(0.5, 0.15, 1.0, 1.0),
            background_color=(1.0, 1.0, 0.0, 0.8),
            size=16,
        )

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
            group = self.in_sync.get()
            det_msg = group["detections"]
            img_msg = group["rgb"]
            depth_msg = group["depth"]
            det_msg = remap_message(
                det_msg, det_msg.getTransformation(), img_msg.getTransformation()
            )

            depth_map = depth_msg.getFrame()
            rgb = img_msg.getCvFrame()

            helper = AnnotationHelper()

            H, W = rgb.shape[:2]

            self._dst_size = (W, H)
            if depth_map.shape != (H, W):
                raise ValueError("Depth and RGB must share aligned pixel geometry")

            assert isinstance(det_msg, dai.ImgDetections)
            for detection in det_msg.detections:
                detection.labelName = self._label_encoding.get(
                    detection.label, "unknown"
                )

            # Plane capture when switch to heightgrid
            if self._plane_capture:
                self._send_outputs(helper, img_msg, depth_msg, self.MODE_PLANE_CAPTURE)
                continue

            m = det_msg.getCvSegmentationMask()
            dets = det_msg.detections
            mask_rgb = m
            if m is not None and m.shape != (H, W):
                raise ValueError("Instance mask must be remapped to RGB geometry")

            # no click show everything
            if self._selection_point is None:
                # draw masks + boxes + labels for ALL detections
                if m is not None and m.size:
                    # assume instance id == detection index (as produced by parser)
                    present_ids = set(int(v) for v in np.unique(m) if v != 255)
                    for idx in present_ids:
                        self._draw_mask(helper, m, idx)
                for d in dets:
                    label_txt = f"{d.labelName} {getattr(d, 'confidence', 0.0):.2f}"
                    self._draw_rotrect_and_label(helper, d, label_txt)

                # emit: annotations + full depth + all dets
                self._send_outputs(helper, img_msg, depth_msg, self.MODE_NOSELECTION)
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
                    present_ids = set(int(v) for v in np.unique(m) if v != 255)
                    for idx in present_ids:
                        self._draw_mask(helper, m, idx)
                for d in dets:
                    label_txt = f"{d.labelName} {getattr(d, 'confidence', 0.0):.2f}"
                    self._draw_rotrect_and_label(helper, d, label_txt)

                self._send_outputs(helper, img_msg, depth_msg, self.MODE_NOSELECTION)

                self.clearSelection()
                self.clearCachedMeasurements()

                continue

            # keep only the chosen detection
            sel_i = kept_idx[0]
            selected_mid = 255

            # pick the mask instance id under the click
            if mask_rgb is not None and mask_rgb.size:
                h_mask, w_mask = mask_rgb.shape[:2]
                px = int(np.clip(sx * w_mask, 0, w_mask - 1))
                py = int(np.clip(sy * h_mask, 0, h_mask - 1))
                selected_mid = (
                    int(mask_rgb[py, px])
                    if mask_rgb is not None and mask_rgb.size
                    else 255
                )

            if m is not None and selected_mid != 255:
                # draw the masks of every detection, measurements only for the selected one
                present_ids = set(int(v) for v in np.unique(m) if v != 255)
                for idx in present_ids:
                    self._draw_mask(helper, m, idx)

                self._poll_measurement_result()

                for i, d in enumerate(dets):
                    if i == sel_i:
                        base = f"{d.labelName} {getattr(d, 'confidence', 0.0):.2f}"
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
                    base = f"{d.labelName} {getattr(d, 'confidence', 0.0):.2f}"
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
                depthF.setBufferMetadataFrom(depth_msg)
                depthF.setInstanceNum(depth_msg.getInstanceNum())
                depthF.setTransformation(depth_msg.getTransformation())

                self._send_outputs(helper, img_msg, depthF, self.MODE_MEASURE)
                continue

            # No valid instance under click - show all (signal NOSELECTION)
            if m is not None and m.size:
                present_ids = set(int(v) for v in np.unique(m) if v != 255)
                for idx in present_ids:
                    self._draw_mask(helper, m, idx)
            for d in dets:
                label_txt = f"{d.labelName} {getattr(d, 'confidence', 0.0):.2f}"
                self._draw_rotrect_and_label(helper, d, label_txt)

            self._send_outputs(helper, img_msg, depth_msg, self.MODE_NOSELECTION)
