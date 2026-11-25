from datetime import timedelta

import cv2
import depthai as dai
from depthai_nodes.node import (
    ImageAlignDepthCorrection,
    ParcelDetector,
    ParcelDimensioner,
    PlaneCalibrationConfig,
    SupportPlaneCalibrator,
)

from nodes import BenchmarkLogger, ParcelController
from preview import PreviewRendererNode
from storage_node import StorageHostNode

RGB_SIZE = (2000, 1500)
MONO_SIZE = (1280, 800)
DEPTH_SIZE = (768, 480)
DEFAULT_FPS = 10


def init_pipeline(pipeline, fps=DEFAULT_FPS, evidence=None, store=None):
    profile = {
        "configured_fps": fps,
        "rgb": RGB_SIZE,
        "left": MONO_SIZE,
        "right": MONO_SIZE,
        "depth": DEPTH_SIZE,
        "depth_source": "NeuralDepth LARGE",
        "depth_alignment": "undistorted RGB 768 x 480",
        "depth_axial_convention": "target_camera_axial_z",
        "images": "unrectified",
        "opencv_threads": cv2.getNumThreads(),
    }
    controller = pipeline.create(
        ParcelController, profile=profile, evidence=evidence, store=store
    )
    if store is not None:
        storage = pipeline.create(StorageHostNode, store=store)
        controller.history_jobs.link(storage.inputJobs)
        storage.outSaved.link(controller.events["saved"])
    streams = {}
    for role, socket in (
        ("color", dai.CameraBoardSocket.CAM_A),
        ("left", dai.CameraBoardSocket.CAM_B),
        ("right", dai.CameraBoardSocket.CAM_C),
    ):
        camera = pipeline.create(dai.node.Camera).build(socket, sensorFps=fps)
        streams[role] = camera.requestOutput(
            RGB_SIZE if role == "color" else MONO_SIZE,
            dai.ImgFrame.Type.NV12 if role == "color" else dai.ImgFrame.Type.GRAY8,
            fps=fps,
            enableUndistortion=False,
        )
        if role == "color":
            depth_target = camera.requestOutput(
                DEPTH_SIZE,
                dai.ImgFrame.Type.NV12,
                resizeMode=dai.ImgResizeMode.STRETCH,
                fps=fps,
                enableUndistortion=True,
            )
    depth = pipeline.create(dai.node.NeuralDepth).build(
        streams["left"], streams["right"], dai.DeviceModelZoo.NEURAL_DEPTH_LARGE
    )
    if depth.getInputSize(dai.DeviceModelZoo.NEURAL_DEPTH_LARGE) != DEPTH_SIZE:
        raise RuntimeError(
            "NeuralDepth LARGE must deliver the evaluated 768 × 480 grid."
        )
    align = pipeline.create(dai.node.ImageAlign)
    align.input.setBlocking(True)
    depth.depth.link(align.input)
    depth_target.link(align.inputAlignTo)
    correction = pipeline.create(ImageAlignDepthCorrection).build(
        alignedDepth=align.outputAligned,
        sourceDepth=align.passthroughInput,
        policy="source_axial_requires_correction",
    )
    cloud = pipeline.create(dai.node.PointCloud)
    cloud.initialConfig.setOrganized(True)
    cloud.initialConfig.setLengthUnit(dai.LengthUnit.MILLIMETER)
    cloud.initialConfig.setTargetCoordinateSystem(dai.CameraBoardSocket.CAM_A)
    correction.out.link(cloud.inputDepth)
    streams["depth"] = correction.out
    streams["axialCorrection"] = correction.result
    streams["pointCloud"] = cloud.outputPointCloud
    scene = pipeline.create(dai.node.Sync)
    scene.setRunOnHost(True)
    scene.setTimestampSource(dai.node.Sync.TimestampSource.DEVICE)
    scene.setSyncThreshold(timedelta(milliseconds=10))
    scene.setSyncAttempts(-1)
    for name, output in streams.items():
        output.link(scene.inputs[name])
    scene.out.link(controller.events["scene"])
    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_UNCALIBRATED, 100)
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(20)
    imu.out.link(controller.events["imu"])
    calibrator = pipeline.create(SupportPlaneCalibrator).build(
        controller.calibration_cloud,
        controller.imu,
        DEPTH_SIZE,
        config=PlaneCalibrationConfig(max_calibration_attempts=12),
    )
    controller.control.link(calibrator.inputControl)
    calibrator.out.link(controller.events["calibration"])
    detector = pipeline.create(ParcelDetector).build(
        *(
            controller.detector_streams[name]
            for name in ("cloud", "color", "left", "right")
        )
    )
    controller.config.link(detector.inputConfig)
    dimensioner = pipeline.create(ParcelDimensioner).build(detector.out)
    detector.out.link(controller.events["detections"])
    dimensioner.out.link(controller.events["measurements"])
    logger = pipeline.create(BenchmarkLogger)
    for prefix, output in (
        ("detector", detector.out),
        ("dimensioner", dimensioner.out),
    ):
        benchmark = pipeline.create(dai.node.BenchmarkIn)
        benchmark.setRunOnHost(True)
        benchmark.sendReportEveryNMessages(1)
        benchmark.logReportsAsWarnings(False)
        output.link(benchmark.input)
        output.link(logger.events[prefix + "_message"])
        benchmark.report.link(logger.events[prefix + "_report"])
    preview = pipeline.create(
        PreviewRendererNode, current_generation=lambda: controller.session.generation
    )
    controller.preview_jobs.link(preview.inputFrames)
    controller.annotations = preview.annotations
    encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=preview.out,
        frameRate=fps,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        keyframeFrequency=max(1, round(fps)),
    )
    controller.encoded_video = encoder.out
    return controller
