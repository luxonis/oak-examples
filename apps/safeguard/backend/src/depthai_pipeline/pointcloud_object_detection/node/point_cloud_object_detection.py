import depthai as dai

from settings.settings import SpatialZone

from .ground_estimator_node import GroundEstimatorNode
from .occupancy_grid_detection import OccupancyGridDetectionNode
from .occupancy_grid_visualization import OccupancyGridVisualizationNode


class PointCloudObjectDetectionNode(dai.node.ThreadedHostNode):
    """Turn a point cloud and IMU stream into obstacles, a grid, and overlays.

    IMU-validated ground fitting removes floor points, then the occupancy grid
    identifies obstacles. Subnodes publish obstacle geometry, a grid image, and
    a point cloud overlay.
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

        self._ground: GroundEstimatorNode = self.createSubnode(GroundEstimatorNode)
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
        self.out_plane_valid = self._ground.out_plane_valid
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

        Args:
            pcl: Organized point cloud of ``pointcloud_size`` (width, height).
            imu: Raw accelerometer readings.
            pointcloud_size: Width and height of the organized point cloud.
            intrinsics: ``(fx, fy, cx, cy)`` for projecting into the color frame.
            frame_size: Width and height of the color frame for annotations.
        """
        self._ground.build(pcl=pcl, imu=imu)

        self._occupancy_detection.build(
            obstacle_pcl=self._ground.out_obstacle,
            plane_valid=self._ground.out_plane_valid,
            intrinsics=intrinsics,
            frame_size=frame_size,
        )

        self._occupancy_visualization.build(
            obstacles=self._occupancy_detection.out_obstacles,
            occupancy_mask=self._occupancy_detection.out_occupancy_mask,
            plane_valid=self._ground.out_plane_valid,
            obstacle_pcl=self._ground.out_obstacle,
            ground_pcl=self._ground.out_ground,
        )

        return self

    def run(self) -> None:
        """Leave processing to the linked subnodes."""
        pass
