import depthai as dai

from settings.settings import GroundRefitMode, SpatialZone

from .ground_estimator_node import GroundEstimatorNode
from .occupancy_grid_detection import OccupancyGridDetectionNode
from .occupancy_grid_visualization import OccupancyGridVisualizationNode


class PointCloudObjectDetectionNode(dai.node.ThreadedHostNode):
    """Compose ground fitting, polar obstacle detection, and visualization.

    RGB and aligned depth form a point cloud. IMU-validated ground fitting
    removes floor points, then the occupancy grid identifies obstacles.
    Subnodes publish obstacle geometry, a grid image, and a point cloud overlay.
    """

    def __init__(
        self,
        hfov_deg: float,
        danger_zone: SpatialZone,
        warning_zone: SpatialZone,
        ground_refit_mode: GroundRefitMode = GroundRefitMode.STATIC,
    ) -> None:
        super().__init__()

        self._danger_zone = danger_zone
        self._warning_zone = warning_zone
        self._ground_refit_mode = ground_refit_mode

        self._rgbd: dai.node.RGBD = self.createSubnode(dai.node.RGBD).build()
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

    def build(
        self,
        aligned_depth: dai.Node.Output,
        rgb_image: dai.Node.Output,
        imu: dai.Node.Output,
        intrinsics: tuple[float, float, float, float],
        frame_size: tuple[int, int],
    ) -> "PointCloudObjectDetectionNode":
        """Wire the RGBD, ground-estimation, grid, and visualization subnodes."""
        rgb_image.link(self._rgbd.inColor)
        aligned_depth.link(self._rgbd.inDepth)

        self._ground.build(
            pcl=self._rgbd.pcl,
            imu=imu,
            refit_mode=self._ground_refit_mode,
        )

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
        )

        return self

    def run(self) -> None:
        """Leave processing to the linked subnodes."""
        pass
