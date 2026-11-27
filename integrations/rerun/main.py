import logging
from functools import partial

import depthai as dai
import rerun as rr

from utils import rerun_logging
from utils.arguments import initialize_argparser
from utils.rig import log_rig

COLOR_VIDEO_SIZE = (1280, 720)
MONO_VIDEO_SIZE = (640, 400)
IMU_RATE_HZ = 100
IMU_BATCH_THRESHOLD = 1
IMU_MAX_BATCH_REPORTS = 10
SYSTEM_LOG_RATE_HZ = 1.0
RVC2_NN_SHAVES = 7
OAK_D_LITE_NN_SHAVES = 4
QUEUE_SIZE = 4

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_, args = initialize_argparser()

device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
fps = args.fps_limit or (20 if platform == "RVC2" else 30)
try:
    calibration = device.getCalibration()
except dai.EepromError:
    logger.warning("The device has no calibration; cameras are shown at the origin.")
    calibration = device.readCalibration()

features = device.getConnectedCameraFeatures()
camera_names = {camera.socket: rerun_logging.camera_name(camera) for camera in features}
video_cameras = [
    camera
    for camera in features
    if {dai.CameraSensorType.COLOR, dai.CameraSensorType.MONO}
    & set(camera.supportedTypes)
]
color_sockets = [
    camera.socket
    for camera in video_cameras
    if dai.CameraSensorType.COLOR in camera.supportedTypes
]
detection_socket = (
    dai.CameraBoardSocket.CAM_A
    if dai.CameraBoardSocket.CAM_A in color_sockets
    else next(iter(color_sockets), None)
)
detection_camera = camera_names.get(detection_socket)
has_depth = bool(device.getStereoPairs()) or any(
    dai.CameraSensorType.TOF in camera.supportedTypes for camera in features
)
has_imu = device.getConnectedIMU() not in ("", "NONE")

rr.script_setup(
    args,
    "oak",
    default_blueprint=rerun_logging.blueprint(
        detection_camera=detection_camera,
        has_depth=has_depth and detection_camera is not None,
        other_cameras=[
            camera_names[camera.socket]
            for camera in video_cameras
            if camera.socket != detection_socket
        ],
        has_imu=has_imu,
    ),
)
imu_frame = log_rig(device, calibration, camera_names)

with dai.Pipeline(device) as pipeline:
    logger.info("Creating pipeline...")
    streams = {}

    camera_nodes = {}
    for camera in video_cameras:
        name = camera_names[camera.socket]
        camera_node = pipeline.create(dai.node.Camera).build(camera.socket)
        camera_nodes[camera.socket] = camera_node
        video = camera_node.requestOutput(
            COLOR_VIDEO_SIZE
            if dai.CameraSensorType.COLOR in camera.supportedTypes
            else MONO_VIDEO_SIZE,
            type=dai.ImgFrame.Type.NV12,
            fps=fps,
            enableUndistortion=True,
        )
        encoder = pipeline.create(dai.node.VideoEncoder).build(
            video,
            frameRate=fps,
            profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
            keyframeFrequency=fps,
        )
        rerun_logging.log_video_codec(name)
        streams[name] = (encoder.out, partial(rerun_logging.log_video, name))

    if detection_socket is not None:
        model = dai.NNModelDescription.fromYamlFile(
            f"yolov6_nano_r2_coco.{platform}.yaml"
        )
        nn_archive = dai.NNArchive(dai.getModelFromZoo(model))
        class_names = nn_archive.getConfig().model.heads[0].metadata.classes
        rerun_logging.log_annotation_context(class_names)
        if has_depth:
            depth = pipeline.create(dai.node.Depth).build(
                dai.node.Depth.Algorithm.AUTO,
                fps=fps,
                size=nn_archive.getInputSize(),
            )
            nn = pipeline.create(dai.node.SpatialDetectionNetwork).build(
                input=camera_nodes[detection_socket],
                depthSource=depth,
                model=nn_archive,
                fps=fps,
            )
            streams["depth"] = (
                nn.passthroughDepth,
                partial(rerun_logging.log_depth, detection_camera),
            )
        else:
            network_input = dai.ImgFrameCapability()
            network_input.fps.fixed(fps)
            network_input.enableUndistortion = True
            nn = pipeline.create(dai.node.DetectionNetwork).build(
                camera_nodes[detection_socket], nn_archive, network_input
            )
        if platform == "RVC2":
            nn.setNNArchive(
                nn_archive,
                numShaves=OAK_D_LITE_NN_SHAVES
                if device.getDeviceName() == "OAK-D-LITE"
                else RVC2_NN_SHAVES,
            )
        nn.input.setBlocking(False)
        nn.input.setMaxSize(1)
        streams["detections"] = (
            nn.out,
            partial(
                rerun_logging.log_detections,
                detection_camera,
                COLOR_VIDEO_SIZE,
                class_names,
            ),
        )

    if has_imu:
        imu = pipeline.create(dai.node.IMU)
        imu.enableIMUSensor(rerun_logging.IMU_SENSORS, IMU_RATE_HZ)
        imu.setBatchReportThreshold(IMU_BATCH_THRESHOLD)
        imu.setMaxBatchReports(IMU_MAX_BATCH_REPORTS)
        rerun_logging.log_imu_static()
        streams["imu"] = (imu.out, partial(rerun_logging.log_imu, imu_frame))

    system_logger = pipeline.create(dai.node.SystemLogger)
    system_logger.setRate(SYSTEM_LOG_RATE_HZ)
    streams["system"] = (system_logger.out, rerun_logging.log_system)

    video_streams = {camera_names[socket] for socket in camera_nodes}
    queues = {
        name: output.createOutputQueue(
            maxSize=QUEUE_SIZE, blocking=name in video_streams
        )
        for name, (output, _) in streams.items()
    }

    logger.info("Pipeline created.")
    pipeline.start()
    logger.info("Pipeline started.")
    while pipeline.isRunning():
        for name, msg in dai.MessageQueue.getAny(queues).items():
            _, log = streams[name]
            log(msg)

rr.script_teardown(args)
