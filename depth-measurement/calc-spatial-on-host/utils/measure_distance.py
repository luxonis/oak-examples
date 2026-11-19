import depthai as dai
import numpy as np
from typing import Tuple


class RegionOfInterest(dai.Buffer):
    def __init__(self, xmin: int, ymin: int, xmax: int, ymax: int) -> None:
        super().__init__(0)
        self._xmin = xmin
        self._ymin = ymin
        self._xmax = xmax
        self._ymax = ymax

    @staticmethod
    def from_size(x: int, y: int, size: int) -> "RegionOfInterest":
        return RegionOfInterest(x - size, y - size, x + size, y + size)

    @property
    def xmin(self) -> int:
        return self._xmin

    @xmin.setter
    def xmin(self, value: int) -> None:
        self._xmin = value

    @property
    def ymin(self) -> int:
        return self._ymin

    @ymin.setter
    def ymin(self, value: int) -> None:
        self._ymin = value

    @property
    def xmax(self) -> int:
        return self._xmax

    @xmax.setter
    def xmax(self, value: int) -> None:
        self._xmax = value

    @property
    def ymax(self) -> int:
        return self._ymax

    @ymax.setter
    def ymax(self, value: int) -> None:
        self._ymax = value

    def get_frame_roi(self, frame: np.ndarray) -> np.ndarray:
        xmin = max(0, self._xmin)
        ymin = max(0, self._ymin)
        xmax = min(frame.shape[1], self._xmax)
        ymax = min(frame.shape[0], self._ymax)
        return frame[ymin:ymax, xmin:xmax]


class Point2d:
    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self._x = value

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        self._y = value


class SpatialDistance(dai.Buffer):
    def __init__(self, centroid: Point2d, spatials: dai.Point3d) -> None:
        super().__init__(0)
        self._centroid = centroid
        self._spatials = spatials

    @property
    def spatials(self) -> dai.Point3f:
        return self._spatials

    @spatials.setter
    def spatials(self, value: dai.Point3f) -> None:
        self._spatials = value

    @property
    def centroid(self) -> Tuple[int, int]:
        return self._centroid

    @centroid.setter
    def centroid(self, value: Tuple[int, int]) -> None:
        self._centroid = value


class MeasureDistance(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput()
        self._threshold_low = 200  # 20cm
        self._threshold_high = 30000  # 30m
        self._averaging_method = np.mean
        self.roi_input = self.createInput()

    def build(
        self,
        depth_frames: dai.Node.Output,
        roi: RegionOfInterest,
    ) -> "MeasureDistance":
        self.link_args(depth_frames)
        self._roi = roi
        return self

    def setAveragingMethod(self, method) -> None:
        self._averaging_method = method

    def process(self, depth_frame: dai.ImgFrame) -> None:
        # print("Measure distance process start")
        self._update_roi()
        depth = depth_frame.getFrame()

        # Calculate the average depth in the ROI.
        depthROI = self._roi.get_frame_roi(depth)
        inRange = (self._threshold_low <= depthROI) & (depthROI <= self._threshold_high)

        if inRange.any():
            averageDepth: float = self._averaging_method(depthROI[inRange])
        else:
            averageDepth = np.nan

        centroid = Point2d(
            int((self._roi.xmax + self._roi.xmin) / 2),
            int((self._roi.ymax + self._roi.ymin) / 2),
        )  # Get centroid of the ROI

        # Depth is in millimeters. Use the produced depth frame's optical frame:
        # +X right, +Y down, +Z forward, including its actual crop/alignment.
        k_inv = np.asarray(depth_frame.getTransformation().getIntrinsicMatrixInv())
        ray = k_inv @ np.array([centroid.x, centroid.y, 1.0])
        xyz = ray * (averageDepth / ray[2])
        spatial_distance = SpatialDistance(centroid, dai.Point3f(*xyz))
        spatial_distance.setTimestamp(depth_frame.getTimestamp())
        spatial_distance.setTimestampDevice(depth_frame.getTimestampDevice())
        spatial_distance.setSequenceNum(depth_frame.getSequenceNum())
        self.output.send(spatial_distance)
        # print("Measure distance process end")

    def _update_roi(self) -> None:
        rois = self.roi_input.tryGetAll()
        if rois:
            self._roi = rois[-1]
        # print("ROI updated")

    def setLowerThreshold(self, threshold_low):
        self._threshold_low = threshold_low

    def setUpperThreshold(self, threshold_high):
        self._threshold_high = threshold_high
