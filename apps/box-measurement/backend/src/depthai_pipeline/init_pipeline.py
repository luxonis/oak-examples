import logging

import depthai as dai
from depthai_nodes.node import (
    BoxMeasurer,
    PlaneCalibrationConfig,
    SupportPlaneCalibrator,
)

from depthai_pipeline.node.support_plane_preview import SupportPlanePreview
from services.support_plane_controller import SupportPlaneController
from util.device_support import check_device_supported

from config import FPS, NEURAL_DEPTH_MODEL, COLOR_RESOLUTION, MONO_RESOLUTION

logger = logging.getLogger(__name__)

VISUALIZER_TOPICS = {
    "color": "Color stream",
    "detections": "Detections",
    "plane_preview_pcl": "Support plane preview",
}


def init_pipeline(
    pipeline: dai.Pipeline,
    confidence_threshold: float,
    visualizer: dai.RemoteConnection,
) -> tuple[SupportPlaneController, BoxMeasurer]:
    fps = FPS
    device = pipeline.getDefaultDevice()
    check_device_supported(device)

    if not device.setIrLaserDotProjectorIntensity(1):
        logger.info(
            "IR laser dot projector is not available on this device; continuing "
            "without it. Depth on plain surfaces may be noisier."
        )

    color_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    left_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    color_out = color_cam.requestOutput(
        COLOR_RESOLUTION, fps=fps, enableUndistortion=True
    )
    left_out = left_cam.requestOutput(MONO_RESOLUTION, fps=fps)
    right_out = right_cam.requestOutput(MONO_RESOLUTION, fps=fps)

    nv12_out = color_cam.requestOutput(
        COLOR_RESOLUTION, type=dai.ImgFrame.Type.NV12, fps=fps
    )
    color_h264 = pipeline.create(dai.node.VideoEncoder).build(
        input=nv12_out,
        frameRate=fps,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
        keyframeFrequency=fps,
    )

    # Neural depth
    model = getattr(dai.DeviceModelZoo, NEURAL_DEPTH_MODEL)
    neural_depth = pipeline.create(dai.node.NeuralDepth).build(
        leftInput=left_out,
        rightInput=right_out,
        model=model,
    )

    # IMU
    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(10)

    # The application owns the aligned measurement grid and high-resolution video.
    nn_width, nn_height = (512, 320)
    measurement_color = pipeline.create(dai.node.ImageManip)
    measurement_color.initialConfig.setOutputSize(
        nn_width, nn_height, dai.ImageManipConfig.ResizeMode.STRETCH
    )
    measurement_color.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    color_out.link(measurement_color.inputImage)

    nn_depth_align = pipeline.create(dai.node.ImageAlign)
    neural_depth.depth.link(nn_depth_align.input)
    measurement_color.out.link(nn_depth_align.inputAlignTo)

    # RGBD
    rgbd = pipeline.create(dai.node.RGBD).build()
    measurement_color.out.link(rgbd.inColor)
    nn_depth_align.outputAligned.link(rgbd.inDepth)

    # Segmentation, tracking, geometry and numerical accumulation belong to
    # depthai-nodes.
    box_measurement = pipeline.create(BoxMeasurer).build(
        color=measurement_color.out,
        pointCloud=rgbd.pcl,
        pointCloudSize=(nn_width, nn_height),
        confidenceThreshold=confidence_threshold,
    )

    # Calibration and measurement receive the same organized cloud.
    calibrator = pipeline.create(SupportPlaneCalibrator).build(
        pointCloud=rgbd.pcl,
        imu=imu.out,
        pointCloudSize=(nn_width, nn_height),
        config=PlaneCalibrationConfig(),
    )
    support_plane = SupportPlaneController(calibrator, box_measurement)
    plane_preview = pipeline.create(SupportPlanePreview).build(
        rgbd.pcl, (nn_width, nn_height), support_plane
    )

    # Visualizer topics
    visualizer.addTopic(VISUALIZER_TOPICS["color"], color_h264.out)
    visualizer.addTopic(VISUALIZER_TOPICS["detections"], box_measurement.out)
    visualizer.addTopic(VISUALIZER_TOPICS["plane_preview_pcl"], plane_preview.out)

    return support_plane, box_measurement
