import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    MPPalmDetectionParser,
    DepthMerger,
    ImgDetectionsFilter,
    ImgDetectionsBridge,
)

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.detection_merger import DetectionMerger
from utils.measure_object_distance import MeasureObjectDistance
from utils.visualize_object_distances import VisualizeObjectDistances
from utils.show_alert import ShowAlert

DANGEROUS_OBJECTS = ["bottle", "cup"]

_, args = initialize_argparser()

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
    left_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_cam.requestOutput(
            obj_det_nn_archive.getInputSize(), fps=args.fps_limit
        ),
        right=right_cam.requestOutput(
            obj_det_nn_archive.getInputSize(), fps=args.fps_limit
        ),
        presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
    )
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    if platform == "RVC2":
        stereo.setOutputSize(*obj_det_nn_archive.getInputSize())
    stereo.setLeftRightCheck(True)
    stereo.setRectification(True)

    camera_output = color_camera.requestOutput(
        (800, 600), dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

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

    adapter = pipeline.create(ImgDetectionsBridge).build(
        palm_det_nn.out, ignore_angle=True
    )

    detection_depth_merger = pipeline.create(DepthMerger).build(
        output_2d=obj_det_nn.out,
        output_depth=stereo.depth,
        calib_data=device.readCalibration2(),
        depth_alignment_socket=dai.CameraBoardSocket.CAM_A,
        shrinking_factor=0.1,
    )
    palm_depth_merger = pipeline.create(DepthMerger).build(
        output_2d=adapter.out,
        output_depth=stereo.depth,
        calib_data=device.readCalibration2(),
        depth_alignment_socket=dai.CameraBoardSocket.CAM_A,
        shrinking_factor=0.1,
    )

    # merge both detections into one message
    merge_detections = pipeline.create(DetectionMerger).build(
        detection_depth_merger.output, palm_depth_merger.output
    )
    merge_detections.set_detection_2_label_offset(len(classes))

    # Filter out everything except for dangerous objects and palm
    merged_labels = classes + ["palm"]
    filter_labels = [merged_labels.index(i) for i in DANGEROUS_OBJECTS]
    filter_labels.append(merged_labels.index("palm"))
    detection_filter = pipeline.create(ImgDetectionsFilter).build(
        merge_detections.output, labels_to_keep=filter_labels
    )

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
        depth=stereo.depth,
    )

    # visualization
    visualizer.addTopic("Color", camera_output)
    visualizer.addTopic("Detections", annotation_node.out_detections)
    visualizer.addTopic("Distances", visualize_distances.output)
    visualizer.addTopic("Alert", show_alert.output)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
