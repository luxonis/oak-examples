import depthai as dai
from pathlib import Path
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
visualizer = dai.RemoteConnection(httpPort=8082)


with dai.Pipeline(device) as pipeline:
    platform = device.getPlatformAsString()

    cam_rgb = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )

    # BLUR
    blur_nn_archive_path = Path(__file__).parent / Path(
        f"models/blur.{platform.lower()}.tar.xz"
    )
    blur_nn_archive = dai.NNArchive(archivePath=str(blur_nn_archive_path))
    nn_blur = pipeline.create(ParsingNeuralNetwork).build(
        cam_rgb, blur_nn_archive, fps=args.fps_limit
    )

    visualizer.addTopic("Blur", nn_blur.out, "images")
    visualizer.addTopic("Passthrough", nn_blur.passthrough, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
