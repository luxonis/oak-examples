"""Build the SafeGuard detection and alert pipeline."""

import logging
import time
from functools import lru_cache
from pathlib import Path

import depthai as dai
import numpy as np
from depthai_nodes.node import ParsingNeuralNetwork

from depthai_pipeline.common.node.danger_classifier import DangerClassifier
from depthai_pipeline.common.node.danger_visualizer import DangerVisualizer
from depthai_pipeline.nn_person_detection.node.segmentation_danger_evaluator import (
    SegmentationDangerEvaluator,
)
from depthai_pipeline.nn_person_detection.node.tracklet_segmentation_matcher import (
    TrackletSegmentationMatcher,
)
from depthai_pipeline.pointcloud_object_detection.node.point_cloud_object_detection import (
    PointCloudObjectDetectionNode,
)
from depthai_pipeline.pointcloud_object_detection.node.pointcloud_danger_evaluator import (
    PointCloudDangerEvaluator,
)
from settings.settings import Settings

MODEL_YAML = (
    Path(__file__).resolve().parent.parent
    / "depthai_models"
    / "yolov8_instance_segmentation_nano.RVC4.yaml"
)
COLOR_SIZE = (1920, 1080)
MONO_SIZE = (640, 480)
log = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _model_from_zoo(platform_name: str):
    """Resolve the bundled model once per process across settings changes."""
    model = dai.NNModelDescription.fromYamlFile(str(MODEL_YAML))
    model.platform = platform_name
    for attempt in range(3):
        try:
            return dai.getModelFromZoo(model)
        except RuntimeError:
            if attempt == 2:
                raise
            log.warning("Model lookup failed; retrying in 2 seconds")
            time.sleep(2)


def init_pipeline(
    pipeline: dai.Pipeline,
    settings: Settings,
    visualizer: dai.RemoteConnection,
) -> tuple[str, ...]:
    """Attach cameras, assessments, alert state, and Visualizer topics.

    Args:
        pipeline: DepthAI pipeline to populate.
        settings: Current runtime settings.
        visualizer: Remote connection used to publish topics.

    Returns:
        Names of registered topics to remove when the pipeline stops.
    """
    device = pipeline.getDefaultDevice()
    color_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    left_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    color_out = color_cam.requestOutput(
        COLOR_SIZE, fps=settings.fps, enableUndistortion=True
    )

    auto_calib = pipeline.create(dai.node.AutoCalibration).build(left_cam, right_cam)
    auto_calib.initialConfig.mode = dai.AutoCalibrationConfig.CONTINUOUS

    preview = color_cam.requestOutput(
        (640, 360),
        type=dai.ImgFrame.Type.RGB888i,
        fps=settings.fps,
        enableUndistortion=True,
    )
    depth = pipeline.create(dai.node.Depth).build(
        dai.node.Depth.Algorithm.AUTO, fps=settings.fps, size=MONO_SIZE
    )
    depth_output = depth.depth
    log.info(
        "Depth backend: %s (config: %s)",
        depth.getResolvedAlgorithm(),
        depth.getResolvedConfig(),
    )

    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 50)
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)

    # Person masks are paired with tracker IDs, aligned depth, and gravity.
    archive = dai.NNArchive(_model_from_zoo(device.getPlatform().name))
    input_size = archive.getInputSize()
    if input_size is None:
        raise ValueError("segmentation model has no input size")
    resize = pipeline.create(dai.node.ImageManip)
    resize.initialConfig.setOutputSize(
        *input_size, dai.ImageManipConfig.ResizeMode.STRETCH
    )
    resize.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    color_out.link(resize.inputImage)

    depth_at_nn = pipeline.create(dai.node.ImageAlign)
    depth_output.link(depth_at_nn.input)
    resize.out.link(depth_at_nn.inputAlignTo)
    nn = pipeline.create(ParsingNeuralNetwork).build(resize.out, archive)
    people = pipeline.create(dai.node.ImgDetectionsFilter)
    people.initialConfig.labelsToKeep = [0]
    nn.out.link(people.inputs["people"])
    tracker = pipeline.create(dai.node.ObjectTracker)
    tracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    people.out.link(tracker.inputDetections)
    color_out.link(tracker.inputTrackerFrame)
    tracked_masks = pipeline.create(TrackletSegmentationMatcher).build(
        tracker.out, people.out
    )
    person_assessment = pipeline.create(SegmentationDangerEvaluator).build(
        tracked_masks.out,
        depth_at_nn.outputAligned,
        imu.out,
        danger_roi=settings.danger_roi,
        warning_roi=settings.warning_roi,
        thresh_low=200,
        thresh_high=30000,
        depth_socket=dai.CameraBoardSocket.CAM_A,
        distance_inside=7,
    )

    # The generic obstacle path is opt-in because point-cloud processing is costly.
    obstacle_assessment = None
    obstacles = None
    if settings.generic_object_detection_enabled:
        pointcloud_size = (COLOR_SIZE[0] // 3, COLOR_SIZE[1] // 3)
        # The preview matches the point-cloud resolution and frame rate.
        color_for_pcl = preview
        depth_for_pcl = pipeline.create(dai.node.ImageAlign)
        color_for_pcl.link(depth_for_pcl.inputAlignTo)
        depth_output.link(depth_for_pcl.input)
        calibration = device.readCalibration2()
        intrinsics = np.asarray(
            calibration.getCameraIntrinsics(
                dai.CameraBoardSocket.CAM_A, *pointcloud_size
            )
        )
        fx, fy = intrinsics[0, 0], intrinsics[1, 1]
        cx, cy = intrinsics[0, 2], intrinsics[1, 2]
        obstacles = pipeline.create(
            PointCloudObjectDetectionNode,
            hfov_deg=calibration.getFov(dai.CameraBoardSocket.CAM_A, useSpec=True),
            danger_zone=settings.danger_roi,
            warning_zone=settings.warning_roi,
        ).build(
            aligned_depth=depth_for_pcl.outputAligned,
            rgb_image=color_for_pcl,
            imu=imu.out,
            intrinsics=(fx, fy, cx, cy),
            frame_size=pointcloud_size,
        )
        obstacle_assessment = (
            pipeline.create(
                PointCloudDangerEvaluator,
                danger_zone=settings.danger_roi,
                warning_zone=settings.warning_roi,
            )
            .build(
                obstacles=obstacles.out_obstacles,
                plane_valid=obstacles.out_plane_valid,
            )
            .out
        )

    alert = pipeline.create(DangerClassifier).build(
        segmentation_assessment=person_assessment.out,
        pointcloud_assessment=obstacle_assessment,
        deescalation_frames=settings.deescalation_sec * settings.fps,
        awareness_escalation_frames=settings.awareness_escalation_sec * settings.fps,
    )
    annotations = pipeline.create(DangerVisualizer).build(alert.out)
    topics = ["color", "danger"]
    visualizer.addTopic("color", preview)
    visualizer.addTopic("danger", annotations.out)
    if obstacles is not None:
        visualizer.addTopic("grid", obstacles.out_grid)
        visualizer.addTopic("grid_annotations", obstacles.out_grid_annotations)
        visualizer.addTopic("obstacle_annotations", obstacles.out_obstacle_annotations)
        visualizer.addTopic("pcl", obstacles.out_pcl)
        topics.extend(("grid", "grid_annotations", "obstacle_annotations", "pcl"))
    return tuple(topics)
