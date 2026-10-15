import argparse
from datetime import timedelta
from pathlib import Path

import depthai as dai

parser = argparse.ArgumentParser(
    description="Filter and merge stereo or multi-device image detections.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
source = parser.add_mutually_exclusive_group()
source.add_argument("--device", help="Stereo device ID or IP; otherwise auto-discover.")
source.add_argument(
    "--devices", nargs="+", help="Multi-device mode: at least two IDs or IPs."
)
parser.add_argument(
    "--calibration", type=Path, help="MultiDeviceCalibration graph JSON."
)
parser.add_argument("--model", default="luxonis/yolov6-nano:r2-coco-512x288")
parser.add_argument("--fps", type=int, choices=range(1, 31), default=10)
parser.add_argument("--confidence", type=float, default=0.5)
parser.add_argument(
    "--labels", nargs="+", type=int, help="Keep these label IDs; COCO person is 0."
)
parser.add_argument(
    "--reject-labels", nargs="+", type=int, help="Reject these label IDs."
)
parser.add_argument(
    "--min-area", type=float, default=0, help="Minimum area in panorama pixels squared."
)
parser.add_argument(
    "--max-detections", type=int, help="Keep at most this many, sorted by confidence."
)
parser.add_argument("--overlap", choices=["off", "nms", "average"], default="nms")
parser.add_argument("--iou", type=float, default=0.4)
parser.add_argument(
    "--projection",
    choices=["Perspective", "Cylindrical", "Equirectangular"],
    default="Cylindrical",
)
parser.add_argument(
    "--no-blend", action="store_true", help="Disable exposure correction and blending."
)
parser.add_argument(
    "--source-masks",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="Restrict detections to their source's visible panorama region.",
)
parser.add_argument(
    "--sync-threshold-ms",
    type=float,
    help="Maximum timestamp spread; defaults to half a frame period.",
)
args = parser.parse_args()

if args.devices and len(args.devices) < 2:
    parser.error("--devices requires at least two devices")
if bool(args.devices) != bool(args.calibration):
    parser.error("--devices and --calibration must be supplied together")
if args.devices and len(set(args.devices)) != len(args.devices):
    parser.error("--devices must contain distinct IDs or IPs")
if args.calibration and not args.calibration.is_file():
    parser.error(f"calibration file does not exist: {args.calibration}")
if not 0.1 <= args.confidence < 1:
    parser.error("--confidence must be at least 0.1 and less than 1")
if not 0 <= args.iou <= 1:
    parser.error("--iou must be between 0 and 1")
if not 0 <= args.min_area < float("inf"):
    parser.error("--min-area must be finite and nonnegative")
if args.max_detections is not None and args.max_detections < 0:
    parser.error("--max-detections must be nonnegative")
if any(label < 0 for label in (args.labels or []) + (args.reject_labels or [])):
    parser.error("label IDs must be nonnegative")
if args.sync_threshold_ms is None:
    args.sync_threshold_ms = 500 / args.fps
if not 0 < args.sync_threshold_ms <= 1000 / args.fps:
    parser.error("--sync-threshold-ms must be positive and at most one frame period")
if not hasattr(dai.node, "ImgDetectionsFilter"):
    parser.error(
        "install the pinned DepthAI build from requirements.txt; see README.md"
    )


def configure_filter(config):
    # Runtime messages replace the complete config, including the CLI filters.
    config.setConfidenceRange(args.confidence)
    config.labelsToKeep = args.labels
    config.labelsToReject = args.reject_labels
    config.setSizeRange(args.min_area)
    config.maxDetections = args.max_detections
    config.sortByConfidence = True
    config.overlapMode = getattr(
        dai.ImgDetectionsFilterConfig.OverlapMode, args.overlap.upper()
    )
    config.overlapIouThreshold = args.iou
    return config


visualizer = dai.RemoteConnection(httpPort=8082)
sync_threshold = timedelta(milliseconds=args.sync_threshold_ms)

with dai.Pipeline(createImplicitDevice=False) as pipeline:
    if args.devices:
        # Apply the graph before creating cameras to establish a common origin.
        calibration = dai.beta.MultiDeviceCalibrationHandler(args.calibration)
        pipeline.setMultiDeviceCalibration(calibration.getGraph())
        sources = [
            (
                pipeline.addDevice(dai.DeviceInfo(identifier)),
                dai.CameraBoardSocket.CAM_A,
            )
            for identifier in args.devices
        ]
    else:
        device = pipeline.addDevice(
            dai.DeviceInfo(args.device) if args.device else dai.Device()
        )
        sources = [
            (device, socket)
            for socket in (dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C)
        ]

    detection_sync = pipeline.create(dai.node.Sync)
    detection_sync.setRunOnHost(True)
    detection_sync.setSyncThreshold(sync_threshold)
    demux = pipeline.create(dai.node.MessageDemux)
    demux.setRunOnHost(True)
    detection_sync.out.link(demux.input)

    unfiltered = pipeline.create(dai.node.ImgDetectionsFilter)
    unfiltered.setRunOnHost(True)
    unfiltered.initialConfig.overlapMode = dai.ImgDetectionsFilterConfig.OverlapMode.OFF
    filtered = pipeline.create(dai.node.ImgDetectionsFilter)
    filtered.setRunOnHost(True)
    configure_filter(filtered.initialConfig)
    config_queue = filtered.inputConfig.createInputQueue(maxSize=1, blocking=False)

    views = []
    for index, (device, socket) in enumerate(sources):
        if socket not in device.getConnectedCameras():
            raise RuntimeError(
                f"Device {device.getDeviceId()} has no {socket.name} camera"
            )
        camera = pipeline.create(dai.node.Camera, device).build(
            socket, sensorFps=args.fps
        )
        model = dai.NNModelDescription(
            args.model, platform=device.getPlatformAsString()
        )
        network = pipeline.create(dai.node.DetectionNetwork, device).build(
            camera, model, fps=args.fps, resizeMode=dai.ImgResizeMode.LETTERBOX
        )
        network.setConfidenceThreshold(0.1)
        key = f"cam{index}"
        network.out.link(detection_sync.inputs[key])
        # Demux outputs are Buffer-typed; declare the type accepted by the filters.
        demux.outputs[key].setPossibleDatatypes(
            [(dai.DatatypeEnum.ImgDetections, False)]
        )
        demux.outputs[key].link(unfiltered.inputs[key])
        demux.outputs[key].link(filtered.inputs[key])
        views.append(
            camera.requestOutput(
                (640, 400),
                type=dai.ImgFrame.Type.NV12,
                fps=args.fps,
                enableUndistortion=True,
            )
        )
        group = f"Camera {index}: {device.getDeviceId()} / {socket.name}"
        visualizer.addTopic(f"Camera {index}", network.passthrough, group)
        visualizer.addTopic(f"Source detections {index}", network.out, group)

    stitching = pipeline.create(dai.node.Stitching).build(views)
    stitching.setRunOnHost(True)
    stitching.setMode(dai.node.Stitching.Mode.PANORAMA)
    stitching.setUseInputCalibration(True)
    stitching.setCameraModel(getattr(dai.CameraModel, args.projection))
    stitching.setMaxPanoramaSize(1280, 800)
    stitching.setSyncThreshold(sync_threshold)
    stitching.setSeamFinder(
        dai.node.Stitching.SeamFinder.NONE
        if args.no_blend
        else dai.node.Stitching.SeamFinder.GRAPHCUT_COLOR
    )
    stitching.out.link(unfiltered.inputReference)
    stitching.out.link(filtered.inputReference)
    if args.source_masks:
        for index in range(len(views)):
            for node in (unfiltered, filtered):
                stitching.outSourceMasks[f"input{index}"].link(
                    node.inputSourceMasks[f"cam{index}"]
                )

    visualizer.addTopic("Unfiltered panorama", stitching.out, "Before filtering")
    visualizer.addTopic("All detections", unfiltered.out, "Before filtering")
    visualizer.addTopic("Filtered panorama", stitching.out, "After filtering")
    visualizer.addTopic("Filtered detections", filtered.out, "After filtering")

    pipeline.start()
    print("Pipeline started.", flush=True)
    visualizer.registerPipeline(pipeline)
    print(
        "1: Off | 2: NMS | 3: Average | W/S: IoU +/-0.05 | "
        "+/-: confidence +/-0.05 | Q: quit"
    )
    print(
        f"Overlap: {args.overlap} | IoU: {args.iou:.2f} | "
        f"Confidence: {args.confidence:.2f}"
    )
    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key in (ord("q"), ord("Q")):
            break
        if key in (ord("1"), ord("2"), ord("3")):
            args.overlap = ("off", "nms", "average")[key - ord("1")]
        elif key in (ord("w"), ord("W"), ord("s"), ord("S")):
            step = 0.05 if key in (ord("w"), ord("W")) else -0.05
            args.iou = min(1.0, max(0.0, round(args.iou + step, 2)))
        elif key in (ord("+"), ord("="), ord("-")):
            step = -0.05 if key == ord("-") else 0.05
            args.confidence = min(0.95, max(0.1, round(args.confidence + step, 2)))
        else:
            continue
        config_queue.send(configure_filter(dai.ImgDetectionsFilterConfig()))
        print(
            f"Overlap: {args.overlap} | IoU: {args.iou:.2f} | "
            f"Confidence: {args.confidence:.2f}"
        )
