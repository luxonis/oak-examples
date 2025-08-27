import depthai as dai
from depthai_nodes.node import ApplyColormap, ParsingNeuralNetwork
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

supported_models = {
    "RVC2": ["luxonis/crestereo:iter2-160x120", "luxonis/crestereo:iter2-320x240"],
    "RVC4": ["luxonis/crestereo:iter4-640x360"],
}
if args.model is not None:
    for key in supported_models.keys():
        if key == platform and args.model not in supported_models[key]:
            raise ValueError(
                f"Model {args.model} is not supported on {platform} platform."
            )
else:
    args.model = supported_models[platform][-1]

if args.fps_limit is None:
    args.fps_limit = 2 if platform == "RVC2" else 5
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # crestereo model
    cre_model_description = dai.NNModelDescription.fromYamlFile(
        f"crestereo.{platform}.yaml"
    )
    if cre_model_description.model != args.model:
        cre_model_description = dai.NNModelDescription(args.model, platform=platform)

    cre_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(cre_model_description))
    model_input_shape = cre_model_nn_archive.getInputSize()

    # stereo camera input
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left.requestOutput(
            model_input_shape, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
        ),
        right=right.requestOutput(
            model_input_shape, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
        ),
        presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
    )

    lr_sync = pipeline.create(dai.node.Sync)
    left.requestOutput(model_input_shape, type=frame_type, fps=args.fps_limit).link(
        lr_sync.inputs["left"]
    )
    right.requestOutput(model_input_shape, type=frame_type, fps=args.fps_limit).link(
        lr_sync.inputs["right"]
    )

    demux = pipeline.create(dai.node.MessageDemux)
    lr_sync.out.link(demux.input)

    nn = pipeline.create(ParsingNeuralNetwork)
    if platform == "RVC4":
        nn.setNNArchive(cre_model_nn_archive)
        nn.setBackend("snpe")
        nn.setBackendProperties(
            {
                "runtime": "dsp",
                "performance_profile": "default",
            }
        )
    elif platform == "RVC2":
        nn.setNNArchive(cre_model_nn_archive, numShaves=7)

    demux.outputs["left"].link(nn.inputs["left"])
    demux.outputs["right"].link(nn.inputs["right"])

    # color stereo disparity
    disparity_coloring = pipeline.create(ApplyColormap).build(stereo.disparity)
    disparity_coloring.setColormap(15)  # cv2.COLORMAP_PLASMA

    # visualization
    visualizer.addTopic("Stereo Disparity", disparity_coloring.out)
    visualizer.addTopic("NN", nn.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
