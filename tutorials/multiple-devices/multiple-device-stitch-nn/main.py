#!/usr/bin/env python3
"""Native host panorama stitching with tiled, on-device YOLO inference."""

from datetime import timedelta
from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    FrameCropper,
    GatherData,
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
    detector = pipeline.create(dai.node.DetectionNetwork).build(cropper.out, archive)
    # Map every tile directly to its matched panorama before suppressing duplicates.
    gathered = pipeline.create(GatherData).build(
        inputData=detector.out,
        inputReference=panorama,
        cameraFps=fps,
        waitCountFn=lambda _: tiles.tileCount,
    )
    merged = pipeline.create(MergeImgDetections).build(input=gathered.out)
    filtered = pipeline.create(dai.beta.node.ImgDetectionsFilter)
    filtered.setRunOnHost(True)
    filtered.initialConfig.nmsDisabled = False
    filtered.initialConfig.nmsConfidenceThreshold = 0.1
    filtered.initialConfig.nmsIouThreshold = 0.2
    merged.out.link(filtered.input)
    return filtered.output


def main():
    parser, args = initialize_argparser()
    if len(args.devices) * len(args.sockets) < 2:
        parser.error("Select at least two camera sources")

    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        visualizer = dai.RemoteConnection(httpPort=8082)
        outputs = []
        for selector in args.devices:
            device = pipeline.addDevice(dai.DeviceInfo(selector))
            for socket in args.sockets:
                camera = pipeline.create(dai.node.Camera, device).build(
                    getattr(dai.CameraBoardSocket, socket), sensorFps=args.fps_limit
                )
                output = camera.requestOutput(
                    IMG_SIZES[args.input_size],
                    dai.ImgFrame.Type.NV12,
                    dai.ImgResizeMode.CROP,
                    fps=args.fps_limit,
                )
                visualizer.addTopic(f"Input-{len(outputs)}", output)
                outputs.append(output)

        stitch = pipeline.create(dai.beta.node.Stitching).build(outputs)
        stitch.setMode(dai.beta.node.Stitching.Mode.PANORAMA)
        # Stitching runs on host by default, supporting RVC2 and RVC4 inputs.
        # Native detection transformTo requires a perspective projection.
        stitch.setCameraModel(dai.CameraModel.Perspective)
        stitch.setContinuous(False)
        stitch.setEstimationFrames(3)
        stitch.setMaxPanoramaSize(4096, 2048)
        stitch.setSeamFinder(dai.beta.node.Stitching.SeamFinder.DP_COLOR)
        stitch.setSyncThreshold(timedelta(milliseconds=100))

        full_detections = add_inference(
            pipeline,
            stitch.out,
            len(outputs),
            args.fps_limit,
        )
        # Publish one detection stream to avoid drawing the same objects twice.
        visualizer.addTopic("Stitched", stitch.out, group="Panorama")
        visualizer.addTopic("PanoramaDetections", full_detections, group="Panorama")

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        print("Open http://localhost:8082. Press r to reset stitching, q to quit.")
        try:
            while pipeline.isRunning():
                pipeline.processTasks()
                key = visualizer.waitKey(1)
                if key == ord("q"):
                    break
                if key == ord("r"):
                    stitch.resetTransform()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
