import depthai as dai
import numpy as np
import json
import time
from collections import deque

from depthai_nodes.utils import AnnotationHelper
from .PointCloudMeasurement import PointCloudMeasurement

BOX_EDGES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)


class MeasurementNode(dai.node.ThreadedHostNode):
    """
    Node for point cloud volume and dimensions measurement

    Inputs:
        - in_pcl            : PointCloudData (RGBD PCL)
        - in_enable_measure : Buffer, holds measuring mode value (0 - disabled, 1 - enabled, 2 - plane capture)
        - in_imu            : IMU packets

    Outputs:
        - out_result : Buffer(JSON)  -> {"dims":[L,W,H], "vol": V}
        - out_ann    : Box/overlay annotation
        - out_plane_status  : Plane status overlay (Calculating / OK / Failed)
    """

    MODE_NOMEASURE = 0
    MODE_MEASURE = 1
    MODE_PLANE = 2

    def __init__(self):
        dai.node.ThreadedHostNode.__init__(self)

        self.in_pcl = self.createInput()
        self.in_enable_measure = self.createInput()
        self.in_imu = self.createInput()

        self.out_result = self.createOutput()
        self.out_ann = self.createOutput()
        self.out_plane_status = self.createOutput()

        self.pcl_measure = PointCloudMeasurement()
        self.have_plane = False
        self.measurement_mode = "obb"  # "obb" | "heightgrid"

        # intrinsics for box outline projection
        self.intrinsics = None
        self.imgW = None
        self.imgH = None

        # smoothing of measurement values
        self._last_dims = deque(maxlen=30)
        self._last_vol = deque(maxlen=30)

        # reference to Annotation node
        self.an_node = None

        # plane / IMU state
        self.fails = 0
        self.g_imu_plane = None
        self.latest_mode = self.MODE_NOMEASURE
        self.latest_imu = None

    def build(
        self, pcl: dai.Node.Output, measure: dai.Node.Output, imu: dai.Node.Output
    ):
        pcl.link(self.in_pcl)
        measure.link(self.in_enable_measure)
        imu.link(self.in_imu)
        return self

    def setIntrinsics(self, fx, fy, cx, cy, imgW, imgH):
        self.intrinsics = (float(fx), float(fy), float(cx), float(cy))
        self.imgW = int(imgW)
        self.imgH = int(imgH)

    def reset_plane(self):
        self.pcl_measure.clear_plane()
        self.have_plane = False
        self.g_imu_plane = None

    def reset_measurements(self):
        self.pcl_measure.from_reset = True
        self._last_dims.clear()
        self._last_vol.clear()
        self.pcl_measure.reset_obb_filter()
        self.pcl_measure.reset_hg_filter()

    # -------------- Emit measurements --------------------
    def push_measurements(self, dims_cm, vol_cm3):
        if dims_cm is not None:
            if dims_cm.size == 3 and np.all(np.isfinite(dims_cm)):
                self._last_dims.append(tuple(float(x) for x in dims_cm))
        if vol_cm3 is not None:
            if isinstance(vol_cm3, (int, float)) and np.isfinite(vol_cm3):
                self._last_vol.append(float(vol_cm3))

    def _emit_median(self, pcl_msg, dims_cm, vol_cm3):
        self.push_measurements(dims_cm, vol_cm3)

        dims_out = None
        vol_out = None

        if self._last_dims:
            arr = np.asarray(self._last_dims, dtype=np.float64)
            dims_out = np.median(arr, axis=0).round(2).tolist()

        if self._last_vol:
            v = np.asarray(self._last_vol, dtype=np.float64)
            vol_out = float(np.median(v).round(2))

        self._emit_result_min(pcl_msg, dims_out, vol_out)

    def _emit_result_min(self, pcl_msg: dai.PointCloudData, dims_cm, volume_cm3):
        payload = {
            "dims": [round(float(x), 2) for x in dims_cm]
            if dims_cm is not None
            else None,
            "vol": round(float(volume_cm3), 2) if volume_cm3 is not None else None,
        }
        b = dai.Buffer()
        b.setData(json.dumps(payload).encode("utf-8"))
        b.setTimestamp(pcl_msg.getTimestamp())
        b.setSequenceNum(pcl_msg.getSequenceNum())
        self.out_result.send(b)

    # ---------------- Projection / overlay helpers ---------------
    def _proj_cam_to_rgb_norm(self, pts_cam):
        if not self.intrinsics:
            return [None] * len(pts_cam)
        fx, fy, cx, cy = self.intrinsics
        out = []
        for x, y, z in np.asarray(pts_cam, float):
            if z <= 0:
                out.append(None)
                continue
            u = fx * (x / z) + cx
            v = fy * (y / z) + cy
            out.append((u / self.imgW, v / self.imgH))
        return out

    def _emit_overlay(
        self,
        pcl_msg: dai.PointCloudData,
        pts3d: np.ndarray,
        edges: np.ndarray | None = None,
        color=(0.0, 1.0, 0.0, 1.0),
        thickness: int = 3,
    ) -> None:
        """
        Draw a wireframe overlay.

        - If 'edges' is provided: draws segments defined by (i,j) pairs over pts3d (OBB case).
        - If 'edges' is None and len(pts3d) == 8: assumes a box and uses BOX_EDGES (height-grid case).
        """
        helper = AnnotationHelper()

        if pts3d is None or len(pts3d) == 0:
            self.out_ann.send(
                helper.build(pcl_msg.getTimestamp(), pcl_msg.getSequenceNum())
            )
            return

        segs = edges
        if segs is None:
            if len(pts3d) == 8:
                segs = BOX_EDGES
            else:
                self.out_ann.send(
                    helper.build(pcl_msg.getTimestamp(), pcl_msg.getSequenceNum())
                )
                return

        pts2d = self._proj_cam_to_rgb_norm(pts3d)

        for i, j in segs:
            pi, pj = pts2d[i], pts2d[j]
            if pi and pj:
                helper.draw_line(pi, pj, color=color, thickness=thickness)

        self.out_ann.send(
            helper.build(pcl_msg.getTimestamp(), pcl_msg.getSequenceNum())
        )

    # ---------------- Height-grid method helpers ---------------
    def _moved_since_plane(
        self,
        g_now: np.ndarray,
        angle_deg_thresh: float = 3.0,
        acc_std_thresh: float = 0.20,
    ) -> bool:
        """
        Returns True if the camera orientation/accel changed enough to invalidate the plane.
        - angle between g vectors > angle_deg_thresh  (default ~3°)
        - OR accel noise (std of recent window) is high (optional jitter guard)
        """
        if not hasattr(self, "g_imu_plane") or self.g_imu_plane is None:
            return False

        # Angle change test (orientation)
        g_now_n = g_now / (np.linalg.norm(g_now) + 1e-9)
        cosang = float(np.clip(np.dot(self.g_imu_plane, g_now_n), -1.0, 1.0))
        ang_deg = float(np.degrees(np.arccos(cosang)))
        if ang_deg > angle_deg_thresh:
            return True
        return False

    def _status_style(self, s):
        if s == "ok":
            return "OK — plane captured", (0.10, 0.85, 0.10, 1.0)
        if s == "calculating":
            return "Calculating plane… hold still", (1.00, 0.75, 0.00, 1.0)
        if s == "failed":
            return "Failed — adjust camera view to include ground plane", (
                0.95,
                0.20,
                0.20,
                1.0,
            )

    def _emit_plane_status(self, pcl_msg, status: str):
        helper = AnnotationHelper()

        label, dot = self._status_style(status)

        pad_x, pad_y = 0.02, 0.02
        font_px = 18
        s = font_px / self.imgH

        BASELINE_OFFSET = 0.90
        ASCENT_CENTER = 0.38
        DOT_RADIUS = 0.60
        GAP_AFTER_DOT = 0.055

        baseline_y = pad_y + BASELINE_OFFSET * s
        cy = baseline_y - ASCENT_CENTER * s
        dot_r = DOT_RADIUS * s
        dot_cx = pad_x + 0.025

        helper.draw_circle(
            (dot_cx, cy), dot_r, outline_color=dot, fill_color=dot, thickness=1
        )
        helper.draw_text(
            label,
            (pad_x + GAP_AFTER_DOT, baseline_y),
            color=dot,
            size=18,
        )

        self.out_plane_status.send(
            helper.build(pcl_msg.getTimestamp(), pcl_msg.getSequenceNum())
        )

    def _extract_g_imu(self, imu_msg):
        if not imu_msg:
            return None
        for pkt in imu_msg.packets:
            if hasattr(pkt, "acceleroMeter") and pkt.acceleroMeter is not None:
                a = pkt.acceleroMeter
                return np.array([a.x, a.y, a.z], dtype=np.float64)
        return None

    def run(self):
        while self.isRunning():
            read_any = False

            while True:
                mb = self.in_enable_measure.tryGet()
                if not mb:
                    break
                try:
                    self.latest_mode = int(bytes(mb.getData())[0])
                except Exception:
                    self.latest_mode = self.MODE_NOMEASURE
                read_any = True

            while True:
                imu_msg = self.in_imu.tryGet()
                if not imu_msg:
                    break
                self.latest_imu = imu_msg
                read_any = True

            processed = False
            while True:
                pcl_msg = self.in_pcl.tryGet()
                if not pcl_msg:
                    break
                processed = True

                mode_val = self.latest_mode
                try:
                    points, colors = pcl_msg.getPointsRGB()
                except Exception as e:
                    print("MeasurementNode: getPointsRGB() failed:", e)
                    continue
                if points is None or len(points) == 0:
                    continue

                if mode_val == self.MODE_PLANE:
                    g_imu = self._extract_g_imu(self.latest_imu)
                    if g_imu is None:
                        continue

                    self.pcl_measure.set_point_cloud_plane(points)
                    plane, _, ok = self.pcl_measure.fit_plane(g_imu)

                    if ok:
                        self.pcl_measure.plane_eq = plane
                        self.have_plane = True
                        self.an_node.requestPlaneCapture(False)
                        self.g_imu_plane = g_imu / (np.linalg.norm(g_imu) + 1e-9)
                        self._emit_plane_status(pcl_msg, "ok")
                        self.fails = 0

                    else:
                        self.fails += 1
                        self.have_plane = False
                        self.an_node.requestPlaneCapture(True)
                        if self.fails > 5:
                            self._emit_plane_status(pcl_msg, "failed")
                        time.sleep(0.005)
                    continue

                if mode_val != self.MODE_MEASURE:
                    if self.measurement_mode == "heightgrid" and self.have_plane:
                        self._emit_plane_status(pcl_msg, "ok")
                    continue

                bgr = colors[:, :3]
                rgb = bgr[:, ::-1].astype(np.float64) / 255.0

                if self.measurement_mode == "obb":
                    self.an_node.requestPlaneCapture(False)
                    self.pcl_measure.set_point_cloud(points, rgb)
                    self.pcl_measure.get_measurement_OBB()

                    self._emit_overlay(pcl_msg, self.pcl_measure.obb_pts)
                    self._emit_median(
                        pcl_msg, self.pcl_measure.dimensions, self.pcl_measure.volume
                    )

                elif self.measurement_mode == "heightgrid":
                    if not self.have_plane or self.pcl_measure.plane_eq is None:
                        self.an_node.requestPlaneCapture(True)
                        self._emit_plane_status(pcl_msg, "calculating")
                        self._emit_result_min(pcl_msg, None, None)
                        continue

                    g_imu = self._extract_g_imu(self.latest_imu)
                    if (
                        g_imu is None
                        or not self.pcl_measure.is_ground_plane(
                            g_imu, self.pcl_measure.plane_eq
                        )
                        or self._moved_since_plane(g_imu)
                    ):
                        self.have_plane = False
                        self.an_node.requestPlaneCapture(True)
                        self._emit_plane_status(pcl_msg, "calculating")
                        self._emit_result_min(pcl_msg, None, None)
                        continue

                    self.pcl_measure.set_point_cloud(points, rgb)
                    self.pcl_measure.get_measurement_groundHG()

                    self._emit_overlay(pcl_msg, self.pcl_measure.corners3d)
                    self._emit_median(
                        pcl_msg, self.pcl_measure.dimensions, self.pcl_measure.volume
                    )
                    self._emit_plane_status(pcl_msg, "ok")

            if not (read_any or processed):
                time.sleep(0.002)
