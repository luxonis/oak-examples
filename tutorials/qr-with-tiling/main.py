from pathlib import Path

import depthai as dai
from depthai_nodes.node import (
    CoordinatesMapper,
    FrameCropper,
    GatherData,
    ImgDetectionsFilter,
    ParsingNeuralNetwork,
    Tiling,
)
from utils.arguments import initialize_argparser
from utils.merge_img_detections import MergeImgDetections
from utils.host_qr_scanner import QRScanner

_, args = initialize_argparser()

IMG_SIZES = {"2160p": (3840, 2160), "1080p": (1920, 1080), "720p": (1280, 720)}
IMG_SHAPE = IMG_SIZES[args.input_size]
OVERLAP = 0.2
GRID_MATRIX = None
GLOBAL_DETECTION = False

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()
    frame_type = (
        dai.ImgFrame.Type.BGR888i
        if platform == dai.Platform.RVC4
        else dai.ImgFrame.Type.BGR888p
    )
    model_description = dai.NNModelDescription.fromYamlFile(
        f"qrdet_nano.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        replay.setFps(args.fps_limit)
        replay.setSize(IMG_SHAPE)
        cam_out = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(IMG_SHAPE, type=frame_type, fps=args.fps_limit)

    grid_size = (args.rows, args.columns)

    tile_manager = pipeline.create(Tiling).build(
        canvasShape=IMG_SHAPE,
        overlap=OVERLAP,
        gridSize=grid_size,
        gridMatrix=GRID_MATRIX,
        globalDetection=GLOBAL_DETECTION,
        resizeShape=nn_archive.getInputSize(),
        resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )

    tiling_cropper = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(
            inputManipConfigs=tile_manager.out,
            maxOutputFrameSize=nn_archive.getInputWidth()
            * nn_archive.getInputHeight()
            * 3,
            waitForConfig=False,
        )
        .build(
            inputImage=cam_out,
        )
    )

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input=tiling_cropper.out, nnSource=nn_archive
    )

    detections_in_image_space = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=cam_out,
        fromTransformationInput=nn.out,
    )

    gathered_detections = pipeline.create(GatherData).build(
        inputData=detections_in_image_space.out,
        inputReference=cam_out,
        cameraFps=args.fps_limit,
        waitCountFn=lambda _: tile_manager.tileCount,
    )

    merged_detections = pipeline.create(MergeImgDetections).build(
        input=gathered_detections.out
    )

    filtered_detections = (
        pipeline.create(ImgDetectionsFilter)
        .useNms(
            confThresh=0.3,
            iouThresh=0.2,
        )
        .build(input=merged_detections.out)
    )

    tile_positions = tile_manager._computeTilePositions(
        overlap=OVERLAP,
        grid_size=grid_size,
        canvas_shape=IMG_SHAPE,
        grid_matrix=GRID_MATRIX,
        global_detection=GLOBAL_DETECTION,
    )

    scanner = pipeline.create(QRScanner).build(
        preview=cam_out, nn=filtered_detections.out, tile_positions=tile_positions
    )
    scanner.inputs["detections"].setBlocking(False)
    scanner.inputs["detections"].setMaxSize(2)
    scanner.inputs["preview"].setBlocking(False)
    scanner.inputs["preview"].setMaxSize(2)

    visualizer.addTopic("Video", cam_out, "images")
    visualizer.addTopic("Visualizations", scanner.out, "images")
    visualizer.addTopic("Tiling grid", scanner.out_grid, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
