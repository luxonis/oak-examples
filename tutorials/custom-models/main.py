import depthai as dai
from pathlib import Path
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.colorize_diff import ColorizeDiff

NN_DIFF_SIZE = (720, 720)
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
    cam_rgb_diff_out = cam_rgb.requestOutput(
        size=NN_DIFF_SIZE,
        type=dai.ImgFrame.Type.BGR888i
        if platform == "RVC4"
        else dai.ImgFrame.Type.BGR888p,
        fps=args.fps_limit,
    )

    # BLUR
    blur_nn_archive_path = Path(__file__).parent / Path(
        f"models/blur.{platform.lower()}.tar.xz"
    )
    blur_nn_archive = dai.NNArchive(archivePath=str(blur_nn_archive_path))
    nn_blur = pipeline.create(ParsingNeuralNetwork).build(cam_rgb_out, blur_nn_archive)

    # EDGE
    edge_nn_archive_path = Path(__file__).parent / Path(
        f"models/edge.{platform.lower()}.tar.xz"
    )
    edge_nn_archive = dai.NNArchive(archivePath=str(edge_nn_archive_path))
    nn_edge = pipeline.create(ParsingNeuralNetwork).build(cam_rgb_out, edge_nn_archive)

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

    script = pipeline.create(dai.node.Script)
    script.setScript("""
    old = node.io['in'].get()
    while True:
        frame = node.io['in'].get()
        node.io['img1'].send(old)
        node.io['img2'].send(frame)
        old = frame
    """)
    cam_rgb_diff_out.link(script.inputs["in"])

    # DIFF
    diff_nn_archive_path = Path(__file__).parent / Path(
        f"models/diff.{platform.lower()}.tar.xz"
    )
    diff_nn_archive = dai.NNArchive(archivePath=str(diff_nn_archive_path))
    nn_diff = pipeline.create(dai.node.NeuralNetwork)
    nn_diff.setNNArchive(diff_nn_archive)
    script.outputs["img1"].link(nn_diff.inputs["img1"])
    script.outputs["img2"].link(nn_diff.inputs["img2"])
    diff_color = pipeline.create(ColorizeDiff).build(nn=nn_diff.out)

    visualizer.addTopic("Blur", nn_blur.out, "images")
    visualizer.addTopic("Edge", nn_edge.out, "images")
    visualizer.addTopic("Concat", nn_concat.out, "images")
    visualizer.addTopic("Diff", diff_color.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
