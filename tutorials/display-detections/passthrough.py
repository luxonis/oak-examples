import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

_, args = initialize_argparser()


device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

visualizer = dai.RemoteConnection(httpPort=8082)


with dai.Pipeline(device) as pipeline:
    platform = device.getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )

    cam = pipeline.create(dai.node.Camera).build()
    cam_out = cam.requestOutput(
        (512, 288),
        fps=args.fps_limit,
        type=dai.ImgFrame.Type.BGR888i
        if platform == dai.Platform.RVC4
        else dai.ImgFrame.Type.BGR888p,
    )

    nn = pipeline.create(ParsingNeuralNetwork).build(cam_out, model_description)

    filter_dets = pipeline.create(dai.node.ImgDetectionsFilter)
    filter_dets.initialConfig.labelsToReject = [57]
    nn.out.link(filter_dets.inputs["detections"])

    visualizer.addTopic("Passthrough", nn.passthrough)
    visualizer.addTopic("Detections", filter_dets.out)

    print("Pipeline created.")

    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
