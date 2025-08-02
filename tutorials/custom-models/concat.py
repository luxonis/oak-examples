import depthai as dai
from pathlib import Path
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

NN_CONCAT_SIZE = (300, 300)

_, args = initialize_argparser()

device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
visualizer = dai.RemoteConnection(httpPort=8082)


with dai.Pipeline(device) as pipeline:
    platform = device.getPlatformAsString()

    cam_rgb = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )
    cam_left = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_B
    )
    cam_right = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_C
    )

    cam_left_out = cam_left.requestOutput(
        size=NN_CONCAT_SIZE,
        type=dai.ImgFrame.Type.BGR888i
        if platform == "RVC4"
        else dai.ImgFrame.Type.BGR888p,
        fps=args.fps_limit,
    )
    cam_right_out = cam_right.requestOutput(
        size=NN_CONCAT_SIZE,
        type=dai.ImgFrame.Type.BGR888i
        if platform == "RVC4"
        else dai.ImgFrame.Type.BGR888p,
        fps=args.fps_limit,
    )
    cam_rgb_out = cam_rgb.requestOutput(
        size=NN_CONCAT_SIZE,
        type=dai.ImgFrame.Type.BGR888i
        if platform == "RVC4"
        else dai.ImgFrame.Type.BGR888p,
        fps=args.fps_limit,
    )

    # CONCAT
    concat_nn_archive_path = Path(__file__).parent / Path(
        f"models/concat.{platform.lower()}.tar.xz"
    )
    concat_nn_archive = dai.NNArchive(archivePath=str(concat_nn_archive_path))
    nn_concat = pipeline.create(ParsingNeuralNetwork)
    nn_concat.setNNArchive(concat_nn_archive)
    cam_rgb_out.link(nn_concat.inputs["img1"])
    cam_left_out.link(nn_concat.inputs["img2"])
    cam_right_out.link(nn_concat.inputs["img3"])

    visualizer.addTopic("Concat", nn_concat.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
