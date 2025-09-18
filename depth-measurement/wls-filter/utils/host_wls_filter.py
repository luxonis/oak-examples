import cv2
import depthai as dai
import numpy as np
import math
from typing import Tuple
from depthai_nodes.utils import AnnotationHelper


class Filter:
    def __init__(self, _lambda, _sigma) -> None:
        self._lambda = _lambda
        self._sigma = _sigma
        self.wlsFilter = cv2.ximgproc.createDisparityWLSFilterGeneric(False)

    def increase_lambda(self) -> None:
        if self._lambda < 255 * 100:
            self._lambda += 100

    def decrease_lambda(self) -> None:
        if self._lambda > 0:
            self._lambda -= 100

    def increase_sigma(self) -> None:
        if self._sigma < 10:
            self._sigma += 0.1
            self._sigma = round(self._sigma, 2)

    def decrease_sigma(self) -> None:
        if self._sigma > 0:
            self._sigma -= 0.1
            self._sigma = round(self._sigma, 2)

    def filter(
        self, disparity, right, depthScaleFactor
    ) -> Tuple[np.ndarray, np.ndarray]:
        # https://github.com/opencv/opencv_contrib/blob/master/modules/ximgproc/include/opencv2/ximgproc/disparity_filter.hpp#L92
        self.wlsFilter.setLambda(self._lambda)
        # https://github.com/opencv/opencv_contrib/blob/master/modules/ximgproc/include/opencv2/ximgproc/disparity_filter.hpp#L99
        self.wlsFilter.setSigmaColor(self._sigma)
        filteredDisp = self.wlsFilter.filter(disparity, right)

        # Compute depth from disparity (32 levels)
        with np.errstate(divide="ignore"):  # Should be safe to ignore div by zero here
            # raw depth values
            depth = depthScaleFactor / filteredDisp
        depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
        depthFrame = depth.astype(np.uint16)

        return filteredDisp, depthFrame


class WLSFilter(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._filter_window = Filter(_lambda=8000, _sigma=1.5)
        self._baseline = 75  # mm
        self._disp_levels = 96
        self._fov = 71.86

        self.depth_frame = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.filtered_disp = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        disparity: dai.Node.Output,
        rectified_right: dai.Node.Output,
        max_disparity: float,
        baseline,
    ) -> "WLSFilter":
        self.link_args(disparity, rectified_right)
        self._disp_multiplier = 255 / max_disparity
        self._baseline = baseline * 10  # mm
        return self

    def process(self, disparity: dai.ImgFrame, right: dai.ImgFrame) -> None:
        disparity_frame = disparity.getFrame()
        right_frame = right.getFrame()
        focal = disparity_frame.shape[1] / (2.0 * math.tan(math.radians(self._fov / 2)))
        depthScaleFactor = self._baseline * focal
        filteredDisp, depthFrame = self._filter_window.filter(
            disparity_frame, right_frame, depthScaleFactor
        )
        filteredDisp = (filteredDisp * self._disp_multiplier).astype(np.uint8)

        max_value = depthFrame.max()
        if max_value == 0:
            color_arr = np.zeros(
                (depthFrame.shape[0], depthFrame.shape[1], 3),
                dtype=np.uint8,
            )
        else:
            color_arr = cv2.cvtColor(
                ((depthFrame / max_value) * 255).astype(np.uint8),
                cv2.COLOR_GRAY2BGR,
            )

        depth_fr = dai.ImgFrame()
        depth_fr.setCvFrame(color_arr, dai.ImgFrame.Type.BGR888i)
        self.depth_frame.send(depth_fr)

        self.filtered_disp.send(
            self.create_img_frame(filteredDisp, dai.ImgFrame.Type.RAW8)
        )

        annots = AnnotationHelper()

        annots.draw_text(
            "Press 'l'/'L' to increase/decrease lambda (min 0, max 25500)",
            position=(0.02, 0.05),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=8,
        )

        annots.draw_text(
            f"Lambda: {self._filter_window._lambda}",
            position=(0.02, 0.08),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=8,
        )

        annots.draw_text(
            "Press 's'/'S' to increase/decrease sigma (min 0, max 10)",
            position=(0.02, 0.11),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=8,
        )

        annots.draw_text(
            f"Sigma: {self._filter_window._sigma}",
            position=(0.02, 0.13),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=8,
        )

        annots_msg = annots.build(right.getTimestamp(), right.getSequenceNum())
        self.annotations.send(annots_msg)

    def handle_key(self, key: int) -> None:
        if key == ord("l"):
            self._filter_window.decrease_lambda()
        elif key == ord("L"):
            self._filter_window.increase_lambda()
        elif key == ord("s"):
            self._filter_window.decrease_sigma()
        elif key == ord("S"):
            self._filter_window.increase_sigma()

    def create_img_frame(self, frame, type: dai.ImgFrame.Type) -> dai.ImgFrame:
        img_frame = dai.ImgFrame()
        img_frame.setWidth(frame.shape[1])
        img_frame.setHeight(frame.shape[0])
        img_frame.setType(type)
        img_frame.setFrame(frame)

        return img_frame
