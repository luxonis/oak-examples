import depthai as dai

from depthai_pipeline.common.message.danger_assessment import DangerAssessment
from depthai_pipeline.common.message.danger_classification import (
    DangerLevel,
    DangerSource,
)
from settings.settings import SpatialZone
from util.danger_zones import classify_obstacle, max_level

from ..message import Obstacles, PlaneValidity


class PointCloudDangerEvaluator(dai.node.HostNode):
    """Classify detected obstacle points against the configured spatial zones."""

    def __init__(
        self,
        danger_zone: SpatialZone,
        warning_zone: SpatialZone,
    ) -> None:
        super().__init__()
        self._danger_zone = danger_zone
        self._warning_zone = warning_zone

    def build(
        self,
        obstacles: dai.Node.Output,
        plane_valid: dai.Node.Output,
    ) -> "PointCloudDangerEvaluator":
        self.link_args(obstacles, plane_valid)
        return self

    def process(self, obstacles_msg: dai.Buffer, plane_valid_msg: dai.Buffer) -> None:
        """Publish an unavailable assessment when no valid ground plane exists."""
        assert isinstance(obstacles_msg, Obstacles)
        assert isinstance(plane_valid_msg, PlaneValidity)

        assessment = DangerAssessment()
        assessment.source = DangerSource.POINTCLOUD
        assessment.level = DangerLevel.SAFE
        assessment.available = False
        assessment.danger_detections = []
        assessment.nearest_point_mm = None

        if plane_valid_msg.plane_valid:
            obstacle_levels = [
                classify_obstacle(
                    obstacle=obstacle,
                    danger_zone=self._danger_zone,
                    warning_zone=self._warning_zone,
                )
                for obstacle in obstacles_msg.obstacles
            ]
            level = max_level(obstacle_levels)
            contributing_obstacles = [
                obstacle
                for obstacle, obstacle_level in zip(
                    obstacles_msg.obstacles, obstacle_levels, strict=True
                )
                if obstacle_level == level and level != DangerLevel.SAFE
            ]

            assessment.available = True
            assessment.level = level

            if contributing_obstacles:
                nearest_obstacle = min(
                    contributing_obstacles,
                    key=lambda obstacle: obstacle.nearest_point_depth,
                )
                point = nearest_obstacle.nearest_point_xyz
                assessment.nearest_point_mm = (
                    float(point[0]),
                    float(point[1]),
                    float(point[2]),
                )

        assessment.setSequenceNum(obstacles_msg.getSequenceNum())
        assessment.setTimestamp(obstacles_msg.getTimestamp())
        assessment.setTimestampDevice(obstacles_msg.getTimestampDevice())
        self.out.send(assessment)
