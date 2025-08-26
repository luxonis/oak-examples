import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.box_processing_node import BoxProcessingNode
from utils.arguments import initialize_argparser
from utils.helper_functions import read_intrinsics


_, args = initialize_argparser()

NN_WIDTH, NN_HEIGHT = 512, 320
INPUT_SHAPE = (NN_WIDTH, NN_HEIGHT)

IMG_WIDTH, IMG_HEIGHT = 640, 400
CAMERA_RESOLUTION = (IMG_WIDTH, IMG_HEIGHT)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(args.device) if args.device else dai.Device()
device.setIrLaserDotProjectorIntensity(1.0)

with dai.Pipeline(device) as p:
    platform = device.getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        f"box_instance_segmentation.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(
        dai.getModelFromZoo(
            model_description,
        )
    )

    color = p.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    color_output = color.requestOutput(
        CAMERA_RESOLUTION, dai.ImgFrame.Type.RGB888i, fps=args.fps_limit
    )

    left = p.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = p.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    stereo = p.create(dai.node.StereoDepth).build(
        left=left.requestOutput(CAMERA_RESOLUTION, fps=args.fps_limit),
        right=right.requestOutput(CAMERA_RESOLUTION, fps=args.fps_limit),
    )

    # Medain filter is only supported on RVC4
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.enableDistortionCorrection(True)
    stereo.setExtendedDisparity(True)
    stereo.setLeftRightCheck(True)
    if platform == dai.Platform.RVC2:  # RVC2 does not support median filter
        stereo.initialConfig.setMedianFilter(dai.MedianFilter.MEDIAN_OFF)

    rgbd = p.create(dai.node.RGBD).build()

    if platform == dai.Platform.RVC4:
        align = p.create(dai.node.ImageAlign)
        stereo.depth.link(align.input)
        color_output.link(align.inputAlignTo)
        align.outputAligned.link(rgbd.inDepth)
    else:
        stereo.depth.link(rgbd.inDepth)
        color_output.link(stereo.inputAlignTo)

    color_output.link(rgbd.inColor)

    manip = p.create(dai.node.ImageManip)
    manip.initialConfig.setOutputSize(*nn_archive.getInputSize())
    manip.initialConfig.setFrameType(
        dai.ImgFrame.Type.BGR888p
        if platform == dai.Platform.RVC2
        else dai.ImgFrame.Type.BGR888i
    )
    manip.setMaxOutputFrameSize(
        nn_archive.getInputSize()[0] * nn_archive.getInputSize()[1] * 3
    )

    color_output.link(manip.inputImage)

    nn = p.create(ParsingNeuralNetwork).build(nn_source=nn_archive, input=manip.out)

    if platform == dai.Platform.RVC2:
        nn.setNNArchive(nn_archive, numShaves=7)

    nn.getParser().setConfidenceThreshold(0.7)
    nn.getParser().setIouThreshold(0.5)
    nn.getParser().setMaskConfidence(0.5)

    box_processing = p.create(BoxProcessingNode)
    box_processing.intrinsics = read_intrinsics(device, NN_WIDTH, NN_HEIGHT)

    rgbd.pcl.link(box_processing.inputPCL)
    nn.passthrough.link(box_processing.inputRGB)
    nn.out.link(box_processing.inputDet)

    outputToVisualize = color.requestOutput(
        (640, 400),
        type=dai.ImgFrame.Type.NV12,
        fps=args.fps_limit,
    )

    visualizer.addTopic("Video Stream", outputToVisualize, "images")
    visualizer.addTopic("Box Detections", box_processing.outputANN, "images")
    visualizer.addTopic("Cuboid Fit", box_processing.outputANNCuboid, "images")
    visualizer.addTopic("Pointcloud", rgbd.pcl, "point_clouds")

    p.start()
    visualizer.registerPipeline(p)

    while p.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
