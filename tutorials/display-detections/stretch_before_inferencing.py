import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

_, args = initialize_argparser()


device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

visualizer = dai.RemoteConnection(httpPort=8082)


class FilterDets(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.output = self.createOutput()

    def build(self, detections: dai.Node.Output):
        self.link_args(detections)
        return self

    def process(self, detections: dai.ImgDetections):
        new_dets = dai.ImgDetections()
        new_dets_list = []
        for detection in detections.detections:
            if detection.label != 57:
                new_dets_list.append(detection)
        new_dets.detections = new_dets_list
        new_dets.setTimestamp(detections.getTimestamp())
        new_dets.setSequenceNum(detections.getSequenceNum())
        self.output.send(new_dets)


with dai.Pipeline(device) as pipeline:
    platform = device.getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )

    cam = pipeline.create(dai.node.Camera).build()
    cam_out = cam.requestOutput(
        (1920, 1440),
        fps=args.fps_limit,
        type=dai.ImgFrame.Type.BGR888i
        if platform == dai.Platform.RVC4
        else dai.ImgFrame.Type.BGR888p,
    )

    stretch_manip = pipeline.create(dai.node.ImageManip)
    stretch_manip.initialConfig.setOutputSize(
        512, 288, dai.ImageManipConfig.ResizeMode.STRETCH
    )
    cam_out.link(stretch_manip.inputImage)

    nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        stretch_manip.out, model_description
    )

    filter_dets = pipeline.create(FilterDets).build(nn.out)

    visualizer.addTopic("Full cam FOV (4:3)", cam_out)
    visualizer.addTopic("Stretched (16:9)", stretch_manip.out)
    visualizer.addTopic("Detections", filter_dets.output)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
