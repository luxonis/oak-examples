import depthai as dai
import numpy as np
from depthai_nodes.message import AutoSupportPlaneResult, SupportPlane

from util.aligned_frame import camera_to_aligned, rotation_from_down_vector

from ..message import SupportPlaneStatus


class SupportPlaneSegmenter(dai.node.ThreadedHostNode):
    """Split each point cloud into support plane and obstacle points.

    Uses the latest passed ``AutoSupportPlaneResult``; until there is one, or
    after a result that did not pass, each frame gets empty clouds and an
    invalid status. Both clouds are rotated into the support-plane-aligned
    frame. Distances and point coordinates are in millimeters.
    """

    # Every this-many-th point of the cloud is classified.
    DOWNSAMPLE_FACTOR = 7
    # Largest distance from the support plane of a support plane point.
    SUPPORT_PLANE_DIST_THR = 45

    SUPPORT_PLANE_COLOR = np.array([80, 200, 80, 255], dtype=np.uint8)

    def __init__(self) -> None:
        super().__init__()
        self.out_obstacle = self.createOutput()
        self.out_support_plane = self.createOutput()
        self.out_status = self.createOutput()

        self._input_pcl = self.createInput()
        self._input_result = self.createInput(blocking=False, queueSize=1)

        self._plane: SupportPlane | None = None
        self._R: np.ndarray | None = None

    def build(
        self, pcl: dai.Node.Output, support_plane: dai.Node.Output
    ) -> "SupportPlaneSegmenter":
        """Connect the point cloud and the ``AutoSupportPlane`` results."""
        pcl.link(self._input_pcl)
        support_plane.link(self._input_result)
        return self

    def run(self) -> None:
        while self.isRunning():
            try:
                pcl_msg = self._input_pcl.get()
                while (result := self._input_result.tryGet()) is not None:
                    self._hold(result)
            except dai.MessageQueue.QueueException:
                return
            assert isinstance(pcl_msg, dai.PointCloudData)
            self._process_pcl(pcl_msg)

    def _hold(self, result: dai.ADatatype) -> None:
        """Keep a passed result's plane and aligned rotation, or drop both."""
        assert isinstance(result, AutoSupportPlaneResult)
        plane = result.plane if result.passed else None
        R = None if plane is None else rotation_from_down_vector(np.array(plane.normal))
        if R is None:
            self._plane, self._R = None, None
        else:
            self._plane, self._R = plane, R

    def _process_pcl(self, pcl_msg: dai.PointCloudData) -> None:
        if self._plane is None or self._R is None:
            no_points = np.empty((0, 3), dtype=np.float32)
            no_colors = np.empty((0, 4), dtype=np.uint8)
            self._send_cloud(self.out_obstacle, pcl_msg, no_points, no_colors)
            self._send_cloud(self.out_support_plane, pcl_msg, no_points, no_colors)
            self._send(self.out_status, pcl_msg, SupportPlaneStatus())
            return

        points, colors = pcl_msg.getPointsRGB()
        points = points[:: self.DOWNSAMPLE_FACTOR]
        colors = colors[:: self.DOWNSAMPLE_FACTOR]
        has_depth = points[:, 2] > 1e-6

        # The plane normal has unit length, so this is the perpendicular distance.
        distance = np.abs(
            points @ np.asarray(self._plane.normal, dtype=np.float32)
            + self._plane.offset_mm
        )
        obstacle = has_depth & (distance >= self.SUPPORT_PLANE_DIST_THR)
        on_plane = has_depth & ~obstacle

        self._send_cloud(
            self.out_obstacle,
            pcl_msg,
            camera_to_aligned(points[obstacle], self._R),
            colors[obstacle],
        )
        self._send_cloud(
            self.out_support_plane,
            pcl_msg,
            camera_to_aligned(points[on_plane], self._R),
            np.tile(self.SUPPORT_PLANE_COLOR, (int(on_plane.sum()), 1)),
        )
        self._send(self.out_status, pcl_msg, SupportPlaneStatus(self._plane, self._R))

    def _send_cloud(
        self,
        output: dai.Node.Output,
        frame: dai.Buffer,
        points: np.ndarray,
        colors: np.ndarray,
    ) -> None:
        msg = dai.PointCloudData()
        msg.setPointsRGB(points.astype(np.float32), colors)
        self._send(output, frame, msg)

    @staticmethod
    def _send(output: dai.Node.Output, frame: dai.Buffer, msg: dai.Buffer) -> None:
        """Send ``msg`` with the timestamp and sequence number of ``frame``."""
        msg.setTimestamp(frame.getTimestamp())
        msg.setSequenceNum(frame.getSequenceNum())
        output.send(msg)
