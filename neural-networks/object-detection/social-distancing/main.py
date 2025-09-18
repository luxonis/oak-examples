import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, DepthMerger

from utils.host_bird_eye_view import BirdsEyeView
from utils.measure_object_distance import MeasureObjectDistance
from utils.host_social_distancing import SocialDistancing
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 10 if platform == "RVC2" else 10
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

available_cameras = device.getConnectedCameras()
if len(available_cameras) < 3:
    raise ValueError(
        "Device must have 3 cameras (color, left and right) in order to run this example."
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # person detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"scrfd_person_detection_25g.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # camera input
    cam = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )
    rgb = cam.requestOutput(
        size=det_model_nn_archive.getInputSize(),
        type=frame_type,
        fps=args.fps_limit,
    )

    left = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_B
    )
    right = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_C
    )

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left.requestOutput(
            det_model_nn_archive.getInputSize(), fps=args.fps_limit
        ),
        right=right.requestOutput(
            det_model_nn_archive.getInputSize(), fps=args.fps_limit
        ),
    )
    stereo.initialConfig.setConfidenceThreshold(255)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(True)
    stereo.setSubpixel(False)
    if platform == "RVC2":
        stereo.setOutputSize(*det_model_nn_archive.getInputSize())

    nn_parser: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input=rgb,
        nn_source=det_model_nn_archive,
    )

    # produce spatial detections
    depth_merger = pipeline.create(DepthMerger).build(
        output_2d=nn_parser.out,
        output_depth=stereo.depth,
        calib_data=device.readCalibration2(),
        depth_alignment_socket=dai.CameraBoardSocket.CAM_A,
        shrinking_factor=0.1,
    )

    # annotation
    bird_eye_view = pipeline.create(BirdsEyeView).build(depth_merger.output)
    measure_obj_dist = pipeline.create(MeasureObjectDistance).build(depth_merger.output)
    social_distancing = pipeline.create(SocialDistancing).build(
        distances=measure_obj_dist.output
    )

    # visualization
    visualizer.addTopic("Video", rgb, "images")
    visualizer.addTopic("Detections", nn_parser.out, "images")
    visualizer.addTopic("Distances", social_distancing.output, "images")
    visualizer.addTopic("Bird-eye view", bird_eye_view.output, "bird-eye")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
