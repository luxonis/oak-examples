import depthai as dai
from depthai_nodes.node import (
    AutoSupportPlane,
    AutoSupportPlaneConfig,
    PlaneCalibrationConfig,
)

from settings.settings import SpatialZone

from .occupancy_grid_detection import OccupancyGridDetectionNode
from .occupancy_grid_visualization import OccupancyGridVisualizationNode
from .support_plane_segmenter import SupportPlaneSegmenter


class PointCloudObjectDetectionNode(dai.node.ThreadedHostNode):
    """Turn a point cloud and IMU stream into obstacles, a grid, and overlays.

    Automatic support plane calibration finds and keeps re-verifying the
    support plane; points off it go to the occupancy grid, which identifies
    obstacles. Subnodes publish obstacle geometry, a grid image, and a point
    cloud overlay.
    """

    def __init__(
        self,
        hfov_deg: float,
        danger_zone: SpatialZone,
        warning_zone: SpatialZone,
    ) -> None:
        super().__init__()

        self._danger_zone = danger_zone
        self._warning_zone = warning_zone

        self._auto_support_plane: AutoSupportPlane = self.createSubnode(
            AutoSupportPlane
        )
        self._segmenter: SupportPlaneSegmenter = self.createSubnode(
            SupportPlaneSegmenter
        )
        self._occupancy_detection: OccupancyGridDetectionNode = self.createSubnode(
            OccupancyGridDetectionNode, hfov_deg=hfov_deg
        )
        self._occupancy_visualization: OccupancyGridVisualizationNode = (
            self.createSubnode(
                OccupancyGridVisualizationNode,
                hfov_deg=hfov_deg,
                danger_zone=self._danger_zone,
                warning_zone=self._warning_zone,
                min_visible_range_mm=OccupancyGridDetectionNode.MIN_VISIBLE_RANGE,
            )
        )

        self.out_obstacles = self._occupancy_detection.out_obstacles
        self.out_support_plane_status = self._segmenter.out_status
        self.out_grid = self._occupancy_visualization.out_grid
        self.out_pcl = self._occupancy_visualization.out_pcl
        self.out_grid_annotations = self._occupancy_visualization.out_grid_annotations
        self.out_obstacle_annotations = (
            self._occupancy_visualization.out_obstacle_annotations
        )

    def build(
        self,
        pcl: dai.Node.Output,
        imu: dai.Node.Output,
        pointcloud_size: tuple[int, int],
        intrinsics: tuple[float, float, float, float],
        frame_size: tuple[int, int],
    ) -> "PointCloudObjectDetectionNode":
        """Wire the subnodes to a camera-frame point cloud in millimeters and the IMU.

        Every pipeline start searches for the support plane afresh.

        Args:
            pcl: Organized point cloud of ``pointcloud_size`` (width, height).
            imu: Raw accelerometer readings.
            pointcloud_size: Width and height of the organized point cloud.
            intrinsics: ``(fx, fy, cx, cy)`` for projecting into the color frame.
            frame_size: Width and height of the color frame for annotations.
        """
        self._auto_support_plane.build(
            pointCloud=pcl,
            imu=imu,
            pointCloudSize=pointcloud_size,
            config=AutoSupportPlaneConfig(
                mode=AutoSupportPlaneConfig.Mode.CONTINUOUS,
                # Capped attempts make a failed search report passed=False, so a
                # lost support plane turns the status invalid instead of being
                # held while the search runs on.
                calibration=PlaneCalibrationConfig(max_calibration_attempts=10),
            ),
        )
        self._segmenter.build(pcl=pcl, support_plane=self._auto_support_plane.out)

        self._occupancy_detection.build(
            obstacle_pcl=self._segmenter.out_obstacle,
            support_plane_status=self._segmenter.out_status,
            intrinsics=intrinsics,
            frame_size=frame_size,
        )

        self._occupancy_visualization.build(
            obstacles=self._occupancy_detection.out_obstacles,
            occupancy_mask=self._occupancy_detection.out_occupancy_mask,
            support_plane_status=self._segmenter.out_status,
            obstacle_pcl=self._segmenter.out_obstacle,
            support_plane_pcl=self._segmenter.out_support_plane,
        )

        return self

    def run(self) -> None:
        """Leave processing to the linked subnodes."""
        pass
