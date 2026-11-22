import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter
from depthai.beta.node import MPPalmDetectionParser

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.detection_merger import DetectionMerger
from utils.measure_object_distance import MeasureObjectDistance
from utils.visualize_object_distances import VisualizeObjectDistances
from utils.show_alert import ShowAlert

DANGEROUS_OBJECTS = ["bottle", "cup"]

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
    # One-slot blocking queues pair each detection with the depth frame from the
    # same production step. The default depth queue is non-blocking and can drop
    # that frame.
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
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
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

    # object detection model
    obj_det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    obj_det_nn_archive = dai.NNArchive(dai.getModelFromZoo(obj_det_model_description))
    classes = obj_det_nn_archive.getConfig().model.heads[0].metadata.classes

    # palm detection model
    palm_det_model_description = dai.NNModelDescription.fromYamlFile(
        f"mediapipe_palm_detection.{platform}.yaml"
    )
    palm_det_nn_archive = dai.NNArchive(dai.getModelFromZoo(palm_det_model_description))

    # camera input
    color_camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

    camera_output = color_camera.requestOutput(
        (800, 600),
        dai.ImgFrame.Type.NV12,
        fps=args.fps_limit,
        enableUndistortion=True,
    )

    depth = pipeline.create(dai.node.Depth)
    depth.build(
        dai.node.Depth.Algorithm.AUTO,
        fps=args.fps_limit,
        size=obj_det_nn_archive.getInputSize(),
    )
    depth.setAlignTo(camera_output)

    obj_det_manip = pipeline.create(dai.node.ImageManip)
    obj_det_manip.initialConfig.setOutputSize(
        512, 288, mode=dai.ImageManipConfig.ResizeMode.STRETCH
    )
    obj_det_manip.initialConfig.setFrameType(frame_type)
    camera_output.link(obj_det_manip.inputImage)

    obj_det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        obj_det_manip.out,
        obj_det_nn_archive,
    )
    if platform == "RVC2":
        obj_det_nn.setNNArchive(
            obj_det_nn_archive, numShaves=7
        )  # TODO: change to numShaves=4 if running on OAK-D Lite

    palm_det_manip = pipeline.create(dai.node.ImageManip)
    palm_det_manip.initialConfig.setOutputSize(
        192, 192, mode=dai.ImageManipConfig.ResizeMode.STRETCH
    )
    palm_det_manip.initialConfig.setFrameType(frame_type)
    camera_output.link(palm_det_manip.inputImage)

    palm_det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        palm_det_manip.out,
        palm_det_nn_archive,
    )
    if platform == "RVC2":
        palm_det_nn.setNNArchive(
            palm_det_nn_archive, numShaves=7
        )  # TODO: change to numShaves=4 if running on OAK-D Lite

    parser: MPPalmDetectionParser = palm_det_nn.getParser(0)
    parser.setConfidenceThreshold(0.7)

    object_spatial = create_spatial_calculator(pipeline, _BOX_SHRINKING_FACTOR)
    obj_det_nn.out.link(object_spatial.inputDetections)
    depth.depth.link(object_spatial.inputDepth)
    palm_spatial = create_spatial_calculator(pipeline, _BOX_SHRINKING_FACTOR)
    palm_det_nn.out.link(palm_spatial.inputDetections)
    depth.depth.link(palm_spatial.inputDepth)

    # merge both detections into one message
    merge_detections = pipeline.create(DetectionMerger).build(
        object_spatial.outputDetections, palm_spatial.outputDetections
    )
    merge_detections.set_detection_2_label_offset(len(classes))

    # Filter out everything except for dangerous objects and palm
    merged_labels = classes + ["palm"]
    filter_labels = [merged_labels.index(i) for i in DANGEROUS_OBJECTS]
    filter_labels.append(merged_labels.index("palm"))
    detection_filter = pipeline.create(ImgDetectionsFilter).build(
        merge_detections.output
    )
    detection_filter.keepLabels(filter_labels)

    # annotation
    measure_object_distance = pipeline.create(MeasureObjectDistance).build(
        nn=detection_filter.out
    )

    visualize_distances = pipeline.create(VisualizeObjectDistances).build(
        measure_object_distance.output
    )

    show_alert = pipeline.create(ShowAlert).build(
        distances=measure_object_distance.output,
        palm_label=merged_labels.index("palm"),
        dangerous_objects=[merged_labels.index(i) for i in DANGEROUS_OBJECTS],
    )

    annotation_node = pipeline.create(AnnotationNode).build(
        detections=detection_filter.out,
        video=camera_output,
        depth=depth.depth,
    )

    # visualization
    visualizer.addTopic("Color", camera_output)
    visualizer.addTopic("Detections", annotation_node.out_detections)
    visualizer.addTopic("Distances", visualize_distances.output)
    visualizer.addTopic("Alert", show_alert.output)

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
