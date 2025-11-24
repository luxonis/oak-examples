from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, TilesPatcher, Tiling
from utils.arguments import initialize_argparser
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
    model_description = dai.NNModelDescription.fromYamlFile(
        f"qrdet_nano.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        replay.setFps(args.fps_limit)
        replay.setSize(IMG_SHAPE)
        cam_out = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            IMG_SHAPE, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
        )

    grid_size = (args.rows, args.columns)

    tile_manager = pipeline.create(Tiling).build(
        img_output=cam_out,
        img_shape=IMG_SHAPE,
        overlap=OVERLAP,
        grid_size=grid_size,
        grid_matrix=GRID_MATRIX,
        global_detection=GLOBAL_DETECTION,
        nn_shape=nn_archive.getInputSize(),
        resize_mode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )

    nn_input = tile_manager.out
    if platform == dai.Platform.RVC4:
        interleaved_manip = pipeline.create(dai.node.ImageManip)
        interleaved_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        tile_manager.out.link(interleaved_manip.inputImage)
        nn_input = interleaved_manip.out

    nn = pipeline.create(ParsingNeuralNetwork).build(nn_input, nn_archive)

    nn.input.setMaxSize(grid_size[0] * grid_size[1])
    nn.input.setBlocking(False)

    patcher = pipeline.create(TilesPatcher).build(
        img_frames=cam_out, nn=nn.out, conf_thresh=0.3, iou_thresh=0.2
    )

    tile_positions = tile_manager._computeTilePositions(
        overlap=OVERLAP,
        grid_size=grid_size,
        img_shape=IMG_SHAPE,
        grid_matrix=GRID_MATRIX,
        global_detection=GLOBAL_DETECTION,
    )

    scanner = pipeline.create(QRScanner).build(
        preview=cam_out, nn=patcher.out, tile_positions=tile_positions
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
