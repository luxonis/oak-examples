import depthai as dai
import numpy as np
import cv2
from depthai_nodes.message.img_detections import (
    ImgDetectionExtended,
    ImgDetectionsExtended,
)
from .helper_functions import reverse_resize_and_pad
import time

from depthai_nodes.utils import AnnotationHelper
from .cuboid_fitter import CuboidFitter

NN_WIDTH, NN_HEIGHT = 512, 320
INPUT_SHAPE = (NN_WIDTH, NN_HEIGHT)

IMG_WIDTH, IMG_HEIGHT = 640, 400


class BoxProcessingNode(dai.node.ThreadedHostNode):
    """Node for processing box detection and annotation."""

    def __init__(self):
        dai.node.ThreadedHostNode.__init__(self)
        self.inputPCL = self.createInput()
        self.inputRGB = self.createInput()
        self.inputDet = self.createInput()

        self.outputANN = self.createOutput()
        self.outputANNCuboid = self.createOutput()

        self.fitter = CuboidFitter()
        self.intrinsics = tuple()
        self.fit = False
        self.helper_det = None
        self.helper_cuboid = None
        self.last_successful_fit = 0
        self.dimensions_cache = None
        self.cache_duration = 1.0  # seconds

    def _draw_mask(self, mask: np.ndarray, idx: int):
        """
        Trace the binary mask for a single instance and draw it as a filled polygon.
        """
        h, w = mask.shape
        binary = (mask == idx).astype(np.uint8)

        if not np.any(binary):
            return

        # Extract mask contours to draw polygon lines
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            # To smooth the mask for visualization (TO DO note: could use this approach for PCL filtering)
            epsilon = 0.01 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            pts = approx.reshape(-1, 2)

            # pts = cnt.reshape(-1, 2)                   # To keep original mask
            norm_pts = [(float(x) / w, float(y) / h) for x, y in pts]
            self.helper_det.draw_polyline(
                norm_pts,
                outline_color=(1.0, 0.5, 0.5, 0.0),  # Color for mask outline
                fill_color=(1.0, 0.5, 0.5, 0.3),
                thickness=1,
                closed=True,
            )

    def _draw_cuboid_outline(self, corners: np.ndarray):
        """Draws the cuboid outline in 3D space based on the corners."""
        if self.intrinsics is None or len(self.intrinsics) != 4:
            print(
                "ERROR: AnnotationNode.intrinsics not properly set or invalid length!"
            )
            return
        fx, fy, cx_i, cy_i = self.intrinsics

        # project & normalize
        pts2d_norm = []
        for x, y, z in corners:
            if z <= 0:
                pts2d_norm.append(None)
            else:
                u = (fx * x / z + cx_i) / NN_WIDTH
                v = (fy * y / z + cy_i) / NN_HEIGHT
                pts2d_norm.append((u, v))

        # draw edges
        edges = [
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
        ]
        for i, j in edges:
            if pts2d_norm[i] and pts2d_norm[j]:
                self.helper_cuboid.draw_line(
                    pts2d_norm[i],
                    pts2d_norm[j],
                    color=(0.0, 1.0, 0.0, 1.0),  # Green
                    thickness=3,
                )

    def _fit_cuboid(
        self,
        idx: int,
        mask: np.ndarray,
        pcl: np.ndarray,
        pcl_color: np.ndarray,
    ):
        """Fits cuboid and draws its 3D outline as lines."""

        mask_bool = mask == idx
        pts3d = pcl.reshape((IMG_HEIGHT, IMG_WIDTH, 3))[mask_bool]
        cols = cv2.cvtColor(pcl_color, cv2.COLOR_BGR2RGB)[mask_bool]

        self.fitter.reset()
        self.fitter.set_point_cloud(pts3d, cols)

        if not self.fitter.fit_orthogonal_planes():
            self.fit = False
            return

        dimensions, corners = self.fitter.calculate_dimensions_corners_MAD()

        # print('Dimensions: ', dimensions)

        self.dimensions = dimensions
        self.fit = True
        self.last_successful_fit = time.time()
        self.dimensions_cache = dimensions

        corners = np.asarray(corners)
        outline = self.fitter.get_3d_lines_o3d(corners)
        corners3d = np.asarray(outline.points)
        self._draw_cuboid_outline(corners3d)

    def _draw_box_and_label(self, det: ImgDetectionExtended) -> None:
        """Draws rotated rect and label"""

        # All annotation coordinates are normalized to the NN input size (512×320)
        rr = det._rotated_rect
        cx, cy = rr.center.x, rr.center.y
        w, h = rr.size.width, rr.size.height
        angle = rr.angle

        color = (1.0, 0.5, 0.5, 1.0)  # Red
        bg_color = (1.0, 1.0, 0.0, 1.0)

        self.helper_det.draw_rotated_rect(
            (cx, cy),
            (w, h),
            angle,
            outline_color=color,
            fill_color=None,
            thickness=2,
        )

        # choose first corner for label
        corners = rr.getPoints()
        corner0 = (corners[0].x, corners[0].y)

        if self.fit:
            label = (
                f"Box ({det._confidence:.2f}) "
                f"{self.dimensions[0]:.1f} x {self.dimensions[1]:.1f} x {self.dimensions[2]:.1f} cm"
            )
        elif self.dimensions_cache is not None and (
            time.time() - self.last_successful_fit < self.cache_duration
        ):
            label = (
                f"Box ({det._confidence:.2f}) "
                f"{self.dimensions_cache[0]:.1f} x {self.dimensions_cache[1]:.1f} x {self.dimensions_cache[2]:.1f} cm"
            )
        else:
            label = f"{'Box'} {det._confidence:.2f}"

        self.helper_det.draw_text(
            label,
            corner0,
            color=color,
            background_color=bg_color,
            size=18,
        )

    def _annotate_detection(
        self, det: ImgDetectionExtended, idx: int, mask: np.ndarray, pcl, pcl_colors
    ):
        """Draw all annotations (mask, 3D box fit, bounding box + label) for a single detection."""
        self._draw_mask(mask, idx)
        self._fit_cuboid(idx, mask, pcl, pcl_colors)
        self._draw_box_and_label(det)

    def run(self):
        while self.isRunning():
            pcl_msg = self.inputPCL.get()
            rgb_msg = self.inputRGB.get()
            det_msg = self.inputDet.get()

            if pcl_msg is None or rgb_msg is None or det_msg is None:
                print(
                    f"AnnotationNode: Missing messages - PCL: {pcl_msg is None}, RGB: {rgb_msg is None}, Det: {det_msg is None}"
                )
                time.sleep(0.005)
                continue

            assert isinstance(pcl_msg, dai.PointCloudData)
            assert isinstance(rgb_msg, dai.ImgFrame)
            assert isinstance(det_msg, ImgDetectionsExtended)
            inPointCloud: dai.PointCloudData = pcl_msg
            inRGB: dai.ImgFrame = rgb_msg
            parser_output: ImgDetectionsExtended = det_msg

            try:
                points, colors = inPointCloud.getPointsRGB()
                if points is None:
                    print("AnnotationNode: Empty PCL points array.")
                    continue

                rgba_img = colors.reshape(IMG_HEIGHT, IMG_WIDTH, 4)
                bgr_img = cv2.cvtColor(rgba_img, cv2.COLOR_BGRA2BGR)
                mask = parser_output._masks._mask
                detections = parser_output.detections
                mask_full = reverse_resize_and_pad(
                    mask, (IMG_WIDTH, IMG_HEIGHT), INPUT_SHAPE
                )  # This is still a heavy operation

                timestamp = inPointCloud.getTimestamp()
                seq_num = inPointCloud.getSequenceNum()

                self.helper_det = AnnotationHelper()
                self.helper_cuboid = AnnotationHelper()

                for idx, det in enumerate(detections):
                    self._annotate_detection(det, idx, mask_full, points, bgr_img)

                ann_msg = self.helper_det.build(timestamp, seq_num)
                ann_msg_cuboid = self.helper_cuboid.build(timestamp, seq_num)

                self.outputANN.send(ann_msg)
                self.outputANNCuboid.send(ann_msg_cuboid)

            except Exception as e:
                print(
                    f"AnnotationNode: Error during processing frame (Seq {inRGB.getSequenceNum()}): {e}"
                )
                import traceback

                traceback.print_exc()
                continue
