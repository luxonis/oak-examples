"""Calibrated multi-device panorama with per-camera YOLO detections merged by ImgDetectionsFilter."""

from datetime import timedelta
from pathlib import Path

import depthai as dai

from utils.arguments import initialize_argparser

MODELS_DIR = Path(__file__).parent / "depthai_models"
VIEW_SIZE = (
    640,
    400,
)  # Camera view sent to the host for stitching, multiplied by --panorama-scale
CONFIDENCE_THRESHOLD = 0.5
OVERLAP_MODES = (
    dai.ImgDetectionsFilterConfig.OverlapMode.OFF,
    dai.ImgDetectionsFilterConfig.OverlapMode.NMS,
    dai.ImgDetectionsFilterConfig.OverlapMode.AVERAGE,
)
STEREO_SOCKETS = (dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C)


def calibrate(device_ids, output, sample_count, known_distance):
    """Estimate the pose between the devices with MultiDeviceCalibration and save it as JSON."""
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        calibration = pipeline.create(dai.beta.node.MultiDeviceCalibration)
        calibration.setSampleCount(sample_count)
        # Devices are free-running; grouping tolerates capture offsets of a static scene.
        calibration.sync.setSyncThreshold(timedelta(seconds=5))

        first_cameras = []
        for identifier in device_ids:
            device = pipeline.addDevice(dai.DeviceInfo(identifier))
            connected = device.getConnectedCameras()
            # A factory-calibrated stereo pair fixes the metric scale; single cameras need --known-distance.
            if all(socket in connected for socket in STEREO_SOCKETS):
                sockets = STEREO_SOCKETS
            elif dai.CameraBoardSocket.CAM_A in connected:
                sockets = (dai.CameraBoardSocket.CAM_A,)
            else:
                raise RuntimeError(
                    f"Device {identifier} needs CAM_A or CAM_B/CAM_C; connected: {connected}"
                )
            print(
                f"Calibrating {device.getDeviceId()} with {', '.join(s.name for s in sockets)}"
            )
            for socket in sockets:
                camera = pipeline.create(dai.node.Camera, device).build(
                    socket, sensorFps=5
                )
                calibration.addCamera(camera.requestFullResolutionOutput(fps=5))
            first_cameras.append((device.getDeviceId(), sockets[0]))

        if known_distance is not None:
            (id_a, socket_a), (id_b, socket_b) = first_cameras[:2]
            calibration.setKnownDistance(
                id_a,
                socket_a,
                id_b,
                socket_b,
                known_distance,
                dai.LengthUnit.CENTIMETER,
            )

        control_queue = calibration.inputControl.createInputQueue()
        result_queue = calibration.calibrationOutput.createOutputQueue()
        pipeline.start()
        print(
            f"Collecting {sample_count} synchronized samples. "
            "Point the cameras at a shared textured scene and keep them still."
        )
        control_queue.send(dai.beta.MultiDeviceCalibrationControl.start())
        result = result_queue.get(timedelta(minutes=3))

    if result is None:
        raise RuntimeError("Calibration timed out")
    if not result.passed or result.graph is None:
        raise RuntimeError(f"Calibration failed: {result.info}")
    if not result.getHandler().toJsonFile(str(output)):
        raise RuntimeError(f"Failed to save calibration to {output}")
    print(f"Calibration saved to {output}")
    print(
        f"Confidence: {result.dataConfidence:.3f}, Sampson error: {result.sampsonError:.4g}"
    )


def make_filter_config(mode_index, iou_threshold):
    # Runtime configs replace every option, so always send a complete one.
    config = dai.ImgDetectionsFilterConfig()
    config.setConfidenceRange(CONFIDENCE_THRESHOLD)
    config.overlapMode = OVERLAP_MODES[mode_index]
    config.overlapIouThreshold = iou_threshold
    return config


def main():
    _, args = initialize_argparser()
    calibration_path = Path(args.calibration)
    if args.calibrate or not calibration_path.exists():
        calibrate(
            args.devices, calibration_path, args.sample_count, args.known_distance
        )
    else:
        print(f"Using calibration {calibration_path}; pass --calibrate to redo it")

    sync_threshold = timedelta(milliseconds=args.sync_threshold_ms)
    mode_index = 2 if args.average else 1
    iou_threshold = 0.4

    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        # Every camera transformation must be expressed in one coordinate system before start.
        handler = dai.beta.MultiDeviceCalibrationHandler(str(calibration_path))
        pipeline.setMultiDeviceCalibration(handler.getGraph())
        visualizer = dai.RemoteConnection(httpPort=8082)

        # Detections from all devices are grouped by host timestamp before merging.
        detection_sync = pipeline.create(dai.node.Sync)
        detection_sync.setRunOnHost(True)
        detection_sync.setSyncThreshold(sync_threshold)
        demux = pipeline.create(dai.node.MessageDemux)
        demux.setRunOnHost(True)
        detection_sync.out.link(demux.input)

        merged = pipeline.create(dai.node.ImgDetectionsFilter)
        merged.initialConfig.setConfidenceRange(CONFIDENCE_THRESHOLD)
        merged.initialConfig.overlapMode = OVERLAP_MODES[mode_index]
        merged.initialConfig.overlapIouThreshold = iou_threshold
        config_queue = merged.inputConfig.createInputQueue(maxSize=1, blocking=False)

        views = []
        for index, identifier in enumerate(args.devices):
            device = pipeline.addDevice(dai.DeviceInfo(identifier))
            platform = device.getPlatform()
            camera = pipeline.create(dai.node.Camera, device).build(
                dai.CameraBoardSocket.CAM_A, sensorFps=args.fps_limit
            )
            # Detect on undistorted frames: boxes mapped from a distorted image are not rectangles.
            network_input = dai.ImgFrameCapability()
            network_input.fps.fixed(args.fps_limit)
            network_input.enableUndistortion = True
            description = dai.NNModelDescription.fromYamlFile(
                str(MODELS_DIR / f"yolov6_nano.{platform.name}.yaml")
            )
            network = pipeline.create(dai.node.DetectionNetwork, device).build(
                camera, description, network_input
            )
            key = f"cam{index}"
            network.out.link(detection_sync.inputs[key])
            # MessageDemux outputs are untyped Buffers; declare the type for the filter inputs.
            demux.outputs[key].setPossibleDatatypes(
                [(dai.DatatypeEnum.ImgDetections, False)]
            )
            demux.outputs[key].link(merged.inputs[key])

            # One undistorted NV12 view per camera feeds both the stitcher and the input preview.
            view = camera.requestOutput(
                (
                    VIEW_SIZE[0] * args.panorama_scale,
                    VIEW_SIZE[1] * args.panorama_scale,
                ),
                type=dai.ImgFrame.Type.NV12,
                fps=args.fps_limit,
                enableUndistortion=True,
            )
            views.append(view)
            if args.show_inputs:
                visualizer.addTopic(f"Input-{index}", view, group=f"Camera-{index}")
                visualizer.addTopic(
                    f"Detections-{index}", network.out, group=f"Camera-{index}"
                )

        stitch = pipeline.create(dai.node.Stitching).build(views)
        stitch.setMode(dai.node.Stitching.Mode.PANORAMA)
        # Compose from the calibrated camera poses instead of image features.
        stitch.setUseInputCalibration(True)
        stitch.setCameraModel(getattr(dai.CameraModel, args.projection))
        stitch.setSeamFinder(
            dai.node.Stitching.SeamFinder.GRAPHCUT_COLOR
            if args.blend
            else dai.node.Stitching.SeamFinder.NONE
        )
        stitch.setMaxPanoramaSize(1600 * args.panorama_scale, 800 * args.panorama_scale)
        stitch.setSyncThreshold(sync_threshold)
        # The panorama transformation is the target frame for every camera's boxes.
        stitch.out.link(merged.inputReference)
        # Source masks let duplicate removal keep the box from the camera visible at that seam.
        for index in range(len(views)):
            stitch.outSourceMasks[f"input{index}"].link(
                merged.inputSourceMasks[f"cam{index}"]
            )

        visualizer.addTopic("Stitched", stitch.out, group="Panorama")
        visualizer.addTopic("PanoramaDetections", merged.out, group="Panorama")

        pipeline.start()
        print("Pipeline started.")
        visualizer.registerPipeline(pipeline)
        print(
            "Open http://localhost:8082. Keys: 1 duplicates off, 2 NMS, 3 average, "
            "W/S IoU +/-0.05, q quit."
        )
        try:
            while pipeline.isRunning():
                pipeline.processTasks()
                key = visualizer.waitKey(1)
                if key == ord("q"):
                    break
                if key in (ord("1"), ord("2"), ord("3")):
                    mode_index = key - ord("1")
                elif key in (ord("w"), ord("W"), ord("s"), ord("S")):
                    step = 0.05 if key in (ord("w"), ord("W")) else -0.05
                    iou_threshold = min(1.0, max(0.0, round(iou_threshold + step, 2)))
                else:
                    continue
                config_queue.send(make_filter_config(mode_index, iou_threshold))
                print(
                    f"Duplicates: {OVERLAP_MODES[mode_index].name}, IoU threshold: {iou_threshold:.2f}"
                )
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
