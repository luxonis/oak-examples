import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

from utils.host_bird_eye_view import BirdsEyeView
from utils.measure_object_distance import MeasureObjectDistance
from utils.host_social_distancing import SocialDistancing
from utils.arguments import initialize_argparser

# DepthMerger averaged every depth pixel in [200, 30000] mm and, for keypoints,
# a 5 px square. Thresholds here are exclusive, so the accepted band is 1 mm
# inside that range. A shrinking factor trims that fraction from each box edge,
# which is the scale `1 - 2 * shrinking_factor` about the box center.
_DEPTH_LOWER_THRESHOLD_MM = 200
_DEPTH_UPPER_THRESHOLD_MM = 30000
_KEYPOINT_RADIUS_PX = 5
# Previous DepthMerger shrinkingFactor. Scale keeps the same center and size.
_BOX_SHRINKING_FACTOR = 0.1

_, args = initialize_argparser()


def create_spatial_calculator(pipeline: dai.Pipeline, shrinking_factor: float):
    calculator = pipeline.create(dai.node.SpatialLocationCalculator)
    calculator.initialConfig.setDepthThresholds(
        _DEPTH_LOWER_THRESHOLD_MM, _DEPTH_UPPER_THRESHOLD_MM
    )
    calculator.initialConfig.setCalculationAlgorithm(
        dai.SpatialLocationCalculatorAlgorithm.AVERAGE
    )
    calculator.initialConfig.setStepSize(1)
    calculator.initialConfig.setBoundingBoxScaleFactor(1.0 - 2.0 * shrinking_factor)
    calculator.initialConfig.setCalculateSpatialKeypoints(True)
    calculator.initialConfig.setKeypointRadius(_KEYPOINT_RADIUS_PX)
    calculator.initialConfig.setUseSegmentation(False)
    calculator.inputDetections.setBlocking(True)
    calculator.inputDetections.setMaxSize(1)
    calculator.inputDepth.setBlocking(True)
    calculator.inputDepth.setMaxSize(1)
    # RVC2 and RVC4 both implement this node on device. Running it on the host
    # would pull the depth frame back to the computer.
    calculator.setRunOnHost(False)
    return calculator


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
    # Undistorted, same size as the detector. Aligned depth clears distortion,
    # and the calculator remaps only when both streams still share that
    # source calibration.
    rgb = cam.requestOutput(
        size=det_model_nn_archive.getInputSize(),
        type=frame_type,
        fps=args.fps_limit,
        enableUndistortion=True,
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
        nnSource=det_model_nn_archive,
    )

    # Align depth to the detector frame. RVC4 StereoDepth rejects inputAlignTo.
    if platform == "RVC2":
        nn_parser.passthrough.link(stereo.inputAlignTo)
        aligned_depth = stereo.depth
    else:
        align = pipeline.create(dai.node.ImageAlign)
        stereo.depth.link(align.input)
        nn_parser.passthrough.link(align.inputAlignTo)
        aligned_depth = align.outputAligned

    # produce spatial detections
    spatial_calculator = create_spatial_calculator(pipeline, _BOX_SHRINKING_FACTOR)
    nn_parser.out.link(spatial_calculator.inputDetections)
    aligned_depth.link(spatial_calculator.inputDepth)

    # annotation
    bird_eye_view = pipeline.create(BirdsEyeView).build(
        spatial_calculator.outputDetections
    )
    measure_obj_dist = pipeline.create(MeasureObjectDistance).build(
        spatial_calculator.outputDetections
    )
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
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
