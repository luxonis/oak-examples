import depthai as dai
import os
from depthai_nodes.node import ApplyColormap

from utils.arguments import initialize_argparser
from utils.frame_editor import FrameEditor
from utils.disparity_to_dets import DisparityToDetections
from utils.annotation_node import AnnotationNode


_, args = initialize_argparser()


SIZE = (640, 400)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # media/camera disparity input
    if args.media_path:
        pipeline.setCalibrationData(
            dai.CalibrationHandler(os.path.join(args.media_path, "calib.json"))
        )

        left = pipeline.create(dai.node.ReplayVideo)
        left.setReplayVideoFile(os.path.join(args.media_path, "left.mp4"))
        left.setOutFrameType(dai.ImgFrame.Type.RAW8)
        left.setSize(SIZE)

        right = pipeline.create(dai.node.ReplayVideo)
        right.setReplayVideoFile(os.path.join(args.media_path, "right.mp4"))
        right.setOutFrameType(dai.ImgFrame.Type.RAW8)
        right.setSize(SIZE)

        left_frame_editor = pipeline.create(FrameEditor, dai.CameraBoardSocket.CAM_B)
        right_frame_editor = pipeline.create(FrameEditor, dai.CameraBoardSocket.CAM_C)

        left.out.link(left_frame_editor.input)
        right.out.link(right_frame_editor.input)

        left_out = left_frame_editor.output
        right_out = right_frame_editor.output
    else:
        left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
        left_out = left.requestOutput(size=SIZE, type=dai.ImgFrame.Type.GRAY8)

        right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
        right_out = right.requestOutput(size=SIZE, type=dai.ImgFrame.Type.GRAY8)

    stereo = pipeline.create(dai.node.StereoDepth).build(left=left_out, right=right_out)
    stereo.initialConfig.setMedianFilter(dai.StereoDepthConfig.MedianFilter.KERNEL_7x7)
    stereo.setLeftRightCheck(True)
    stereo.setSubpixel(False)

    # people detector
    detection_generator = pipeline.create(DisparityToDetections).build(
        disparity=stereo.disparity,
        max_disparity=stereo.initialConfig.getMaxDisparity(),
        roi=(50, 50, 550, 350),
    )

    # object tracking
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    if platform == "RVC2":
        objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    else:
        objectTracker.setTrackerType(dai.TrackerType.SHORT_TERM_IMAGELESS)
    objectTracker.setTrackerIdAssignmentPolicy(
        dai.TrackerIdAssignmentPolicy.SMALLEST_ID
    )

    color_transform_disparity = pipeline.create(ApplyColormap).build(stereo.disparity)
    color_transform_disparity.out.link(objectTracker.inputTrackerFrame)
    color_transform_disparity.out.link(objectTracker.inputDetectionFrame)
    detection_generator.out.link(objectTracker.inputDetections)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        objectTracker.out, axis=args.axis, axis_position=args.axis_position
    )

    # visualization
    visualizer.addTopic("Disparity", color_transform_disparity.out, "disparity")
    visualizer.addTopic("Count", annotation_node.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
