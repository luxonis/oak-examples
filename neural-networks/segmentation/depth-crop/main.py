import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.annotation_node import AnnotationNode

from utils.arguments import initialize_argparser

CAMERA_RESOLUTION = (640, 400)

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if not args.fps_limit:
    args.fps_limit = 10 if platform == "RVC2" else 25
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

if len(device.getConnectedCameras()) < 3:
    raise ValueError(
        "Device must have 3 cameras (color, left and right) in order to run this example."
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # depth estimation model
    model_description = dai.NNModelDescription.fromYamlFile(
        f"deeplab_v3_plus.{platform}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    # camera input
    color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    color_output = color.requestOutput(
        CAMERA_RESOLUTION, dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left.requestOutput(CAMERA_RESOLUTION, fps=args.fps_limit),
        right=right.requestOutput(CAMERA_RESOLUTION, fps=args.fps_limit),
    )
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    if platform == "RVC2":
        stereo.setOutputSize(*CAMERA_RESOLUTION)

    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setOutputSize(*nn_archive.getInputSize())
    manip.initialConfig.setFrameType(
        dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
    )
    manip.setMaxOutputFrameSize(
        nn_archive.getInputSize()[0] * nn_archive.getInputSize()[1] * 3
    )
    color_output.link(manip.inputImage)

    nn = pipeline.create(ParsingNeuralNetwork).build(
        nn_source=nn_archive, input=manip.out
    )

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        preview=color_output,
        disparity=stereo.disparity,
        mask=nn.out,
        max_disparity=stereo.initialConfig.getMaxDisparity(),
    )

    output_segmentation_encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=annotation_node.output_segmentation,
        frameRate=args.fps_limit,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    output_cutout_encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=annotation_node.output_cutout,
        frameRate=args.fps_limit,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    output_depth_encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=annotation_node.output_depth,
        frameRate=args.fps_limit,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    # visualization
    visualizer.addTopic("Segmentation", output_segmentation_encoder.out)
    visualizer.addTopic("Cutout", output_cutout_encoder.out)
    visualizer.addTopic("Depth", output_depth_encoder.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
