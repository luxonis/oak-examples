import logging as log

import depthai as dai

from utils.arguments import initialize_argparser
from utils.audioRecorder import AudioRecorder
from utils.download import list_recordings_service, download_recording_service


log.basicConfig(level=log.INFO)
logger = log.getLogger(__name__)


_, args = initialize_argparser()

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

# Audio recorder (PulseAudio via `parec`)
recorder = AudioRecorder(device=getattr(args, "audio_device", None))


def _svc(name: str, fn, err: str):
    def _inner(_: object | None = None):
        path = fn()
        return {"ok": True, "path": str(path)} if path else {"ok": False, "error": err}

    _inner.__name__ = name
    return _inner


start_recording_service = _svc(
    "start_recording_service", recorder.start, "Failed to start recording"
)
stop_recording_service = _svc(
    "stop_recording_service", recorder.stop, "No recording in progress"
)


visualizer.registerService("Start Recording", start_recording_service)
visualizer.registerService("Stop Recording", stop_recording_service)
visualizer.registerService("List Recordings", list_recordings_service)
visualizer.registerService("Download Recording", download_recording_service)


with dai.Pipeline(device) as pipeline:
    logger.info("Creating pipeline...")

    sensors = device.getConnectedCameraFeatures()
    primary = sensors[0].socket.name if sensors else None

    for sensor in sensors:
        cam = pipeline.create(dai.node.Camera).build(sensor.socket)

        w, h = sensor.width, sensor.height
        req = (w, h) if w <= 1920 and h <= 1080 else (1920, 1080)

        cam_out = cam.requestOutput(
            req,
            dai.ImgFrame.Type.NV12,
            fps=args.fps_limit,
        )

        encoder = pipeline.create(dai.node.VideoEncoder)
        encoder.setDefaultProfilePreset(
            args.fps_limit,
            dai.VideoEncoderProperties.Profile.H264_MAIN,
        )
        cam_out.link(encoder.input)

        # Publish each camera stream under its socket name
        visualizer.addTopic(sensor.socket.name, encoder.out, "images")

        # Also publish the first camera under a stable name for custom frontends
        if primary is not None and sensor.socket.name == primary:
            visualizer.addTopic("Video", encoder.out, "images")

    logger.info("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    logger.info("Pipeline running.")

    try:
        while pipeline.isRunning():
            if visualizer.waitKey(1) == ord("q"):
                logger.info("Got 'q' key from the remote connection. Exiting...")
                break
            pipeline.processTasks()

    finally:
        if recorder.is_recording:
            logger.info("Stopping recording due to shutdown...")
            recorder.stop()
