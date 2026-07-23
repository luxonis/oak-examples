from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ApplyDepthColormap, DepthMerger
from utils.arguments import initialize_argparser
from utils.depth_driven_focus import DepthDrivenFocus

_, args = initialize_argparser()
MODEL_DIR = Path(__file__).resolve().parent / "depthai_models"

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        str(MODEL_DIR / f"yunet.{platform.name}.yaml")
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    color_out = cam.requestOutput(
        nn_archive.getInputSize(),
        type=dai.ImgFrame.Type.NV12,
        fps=args.fps_limit,
        enableUndistortion=True,
    )

    depth = pipeline.create(dai.node.Depth)
    depth.build(
        dai.node.Depth.Algorithm.AUTO,
        fps=args.fps_limit,
        size=nn_archive.getInputSize(),
    )
    depth.setAlignTo(color_out)

    face_det_nn = pipeline.create(ParsingNeuralNetwork).build(cam, nn_archive)
    if platform == dai.Platform.RVC2:
        face_det_nn.setNNArchive(nn_archive, numShaves=7)
    depth_merger = pipeline.create(DepthMerger).build(
        face_det_nn.out, depth.depth, device.readCalibration2()
    )
    depth_color_transform = pipeline.create(ApplyDepthColormap).build(depth.depth)

    depth_driven_focus = pipeline.create(DepthDrivenFocus).build(
        control_queue=cam.inputControl.createInputQueue(),
        face_detection=depth_merger.output,
    )

    visualizer.addTopic("Video", color_out, "images")
    visualizer.addTopic("Visualizations", face_det_nn.out, "images")
    visualizer.addTopic("Depth", depth_color_transform.out, "images")
    visualizer.addTopic("Focus distance", depth_driven_focus.output, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
