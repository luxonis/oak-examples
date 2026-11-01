#!/usr/bin/env python3
"""Native host panorama stitching with optional tiled, on-device YOLO inference."""

import time
from datetime import timedelta
from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    FrameCropper,
    GatherData,
    ImgDetectionsFilter,
    ParsingNeuralNetwork,
    Tiling,
)
from utils.arguments import initialize_argparser
from utils.merge_img_detections import MergeImgDetections

IMG_SIZES = {
    "2160p": (3840, 2160),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (640, 480),
    "360p": (640, 360),
}
AF_DELAY_S = 5.0


def add_inference(pipeline, panorama, source_count, fps):
    # The first explicitly opened device is the inference device, even in a mixed rig.
    platform = pipeline.getDefaultDevice().getPlatform()
    description = dai.NNModelDescription.fromYamlFile(
        str(
            Path(__file__).parent
            / "depthai_models"
            / f"yolov6_nano.{platform.name}.yaml"
        )
    )
    archive = dai.NNArchive(dai.getModelFromZoo(description))
    width, height = archive.getInputSize()
    canvas = (width + (width // 2) * source_count, height)
    manip = pipeline.create(dai.node.ImageManip)
    manip.setRunOnHost(True)
    manip.initialConfig.setOutputSize(*canvas)
    manip.initialConfig.setFrameType(
        dai.ImgFrame.Type.BGR888p
        if platform == dai.Platform.RVC2
        else dai.ImgFrame.Type.BGR888i
    )
    manip.setMaxOutputFrameSize(canvas[0] * canvas[1] * 3)
    panorama.link(manip.inputImage)

    tiles = pipeline.create(Tiling).build(
        canvasShape=canvas,
        overlap=0.5,
        gridSize=(source_count, 1),
        gridMatrix=None,
        globalDetection=False,
        resizeShape=archive.getInputSize(),
        resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )
    cropper = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(
            inputManipConfigs=tiles.out,
            maxOutputFrameSize=width * height * 3,
            waitForConfig=False,
        )
        .build(inputImage=manip.out)
    )
    detector = pipeline.create(ParsingNeuralNetwork).build(
        input=cropper.out, nnSource=archive
    )
    gathered = pipeline.create(GatherData).build(
        inputData=detector.out,
        inputReference=manip.out,
        cameraFps=fps,
        waitCountFn=lambda _: tiles.tileCount,
    )
    merged = pipeline.create(MergeImgDetections).build(input=gathered.out)
    filtered = (
        pipeline.create(ImgDetectionsFilter)
        .useNms(
            confThresh=0.1,
            iouThresh=0.2,
        )
        .build(input=merged.out)
    )
    full_group = pipeline.create(GatherData).build(
        inputData=filtered.out,
        inputReference=panorama,
        cameraFps=fps,
        waitCountFn=lambda _: 1,
    )
    full = pipeline.create(MergeImgDetections).build(input=full_group.out)
    return manip.out, filtered.out, full.out


def main():
    parser, args = initialize_argparser()
    infos = (
        [dai.DeviceInfo(selector) for selector in args.devices]
        if args.devices
        else [
            info
            for info in dai.Device.getAllAvailableDevices()
            if info.platform
            in (dai.XLinkPlatform.X_LINK_MYRIAD_X, dai.XLinkPlatform.X_LINK_RVC4)
            and info.state
            in (
                dai.XLinkDeviceState.X_LINK_UNBOOTED,
                dai.XLinkDeviceState.X_LINK_BOOTLOADER,
                dai.XLinkDeviceState.X_LINK_GATE,
            )
        ]
    )
    if not infos or len(infos) * len(args.sockets) < 2:
        parser.error(
            "Stitching needs at least two sources: use --devices ID ID or --devices ID --sockets CAM_B CAM_C"
        )

    if len(set(args.sockets)) != len(args.sockets):
        parser.error("Duplicate sockets are not supported")
    identities = [info.getDeviceId() or info.name for info in infos]
    if len(set(identities)) != len(identities):
        parser.error("Duplicate devices are not supported")

    with dai.Device(infos[0]) as first, dai.Pipeline(first) as pipeline:
        devices = [first] + [pipeline.addDevice(info) for info in infos[1:]]
        if len({device.getDeviceId() for device in devices}) != len(devices):
            raise RuntimeError("Device selectors resolve to the same camera")
        outputs, focus_controls = [], []
        visualizer = dai.RemoteConnection(httpPort=8082)
        for device in devices:
            if device.getPlatform() not in (dai.Platform.RVC2, dai.Platform.RVC4):
                raise RuntimeError("Only RVC2 and RVC4 are supported")
            print(
                f"Connected: {device.getDeviceId()} {device.getPlatform().name}",
                flush=True,
            )
            features = {
                feature.socket: feature
                for feature in device.getConnectedCameraFeatures()
            }
            for socket_name in args.sockets:
                socket = getattr(dai.CameraBoardSocket, socket_name)
                if socket not in features:
                    raise RuntimeError(f"{device.getDeviceId()} has no {socket_name}")
                camera = pipeline.create(dai.node.Camera, device).build(
                    socket, sensorFps=args.fps_limit
                )
                output = camera.requestOutput(
                    IMG_SIZES[args.input_size],
                    dai.ImgFrame.Type.NV12,
                    dai.ImgResizeMode.CROP,
                    fps=args.fps_limit,
                )
                outputs.append(output)
                visualizer.addTopic(f"Input-{len(outputs) - 1}", output)
                if features[socket].hasAutofocus:
                    focus_controls.append(camera.inputControl.createInputQueue())

        stitch = pipeline.create(dai.beta.node.Stitching).build(outputs)
        stitch.setRunOnHost(True)
        stitch.setMode(dai.beta.node.Stitching.Mode.PANORAMA)
        # Native detection transformTo currently supports pinhole projections.
        stitch.setCameraModel(dai.CameraModel.Perspective)
        stitch.setContinuous(False)
        stitch.setEstimationFrames(args.estimation_frames)
        stitch.setMaxPanoramaSize(*args.max_panorama_size)
        stitch.setSeamFinder(
            getattr(dai.beta.node.Stitching.SeamFinder, args.seam_finder)
        )
        stitch.setSyncThreshold(timedelta(milliseconds=args.sync_threshold_ms))
        visualizer.addTopic("Stitched", stitch.out)
        panorama_queue = stitch.out.createOutputQueue(maxSize=1, blocking=False)
        detection_queue = None
        if not args.no_nn:
            canvas, detections, full_detections = add_inference(
                pipeline,
                stitch.out,
                len(outputs),
                args.fps_limit,
            )
            detection_queue = full_detections.createOutputQueue(
                maxSize=1, blocking=False
            )
            visualizer.addTopic("Inference", canvas)
            visualizer.addTopic("Patcher", detections)
            visualizer.addTopic("PanoramaDetections", full_detections)

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        started = focus_started = time.monotonic()
        focus_enabled, reset_done, received, warned = True, False, 0, False
        detection_messages = 0
        print(
            "Visualizer: http://localhost:8082. Press r to reset registration; q to quit.",
            flush=True,
        )
        try:
            while pipeline.isRunning():
                pipeline.processTasks()
                elapsed = time.monotonic() - started
                key = visualizer.waitKey(1)
                if key == ord("q"):
                    break
                if key == ord("r") or (
                    args.reset_after and elapsed >= args.reset_after and not reset_done
                ):
                    stitch.resetTransform()
                    reset_done = True
                    control = dai.CameraControl()
                    control.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
                    for queue in focus_controls:
                        queue.send(control)
                    focus_started, focus_enabled = time.monotonic(), True
                    print("Registration reset", flush=True)
                if focus_enabled and time.monotonic() - focus_started >= AF_DELAY_S:
                    control = dai.CameraControl()
                    control.setAutoFocusMode(dai.CameraControl.AutoFocusMode.OFF)
                    for queue in focus_controls:
                        queue.send(control)
                    focus_enabled = False
                frame = panorama_queue.tryGet()
                if frame is not None:
                    received += 1
                    if received == 1:
                        print(
                            f"Panorama: {frame.getWidth()}x{frame.getHeight()}, "
                            f"projection={frame.getTransformation().getDistortionModel().name}",
                            flush=True,
                        )
                if detection_queue is not None:
                    detections = detection_queue.tryGet()
                    if detections is not None:
                        detection_messages += 1
                        if detection_messages == 1:
                            print(
                                f"Inference running: {len(detections.detections)} detections in first result",
                                flush=True,
                            )
                if elapsed > 20 and not received and not warned:
                    print(
                        "No panorama yet: check Input topics for overlap/texture and synchronization. "
                        "Native registration waits for valid candidates; no concatenation fallback.",
                        flush=True,
                    )
                    warned = True
                if args.duration and elapsed >= args.duration:
                    if not received:
                        raise RuntimeError(
                            "No panorama produced during the bounded run"
                        )
                    if detection_queue is not None and not detection_messages:
                        raise RuntimeError(
                            "Panorama produced, but no inference results during the bounded run"
                        )
                    break
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            print(
                f"Received {received} panorama frames and {detection_messages} inference messages",
                flush=True,
            )


if __name__ == "__main__":
    main()
