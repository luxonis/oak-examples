import depthai as dai
from pathlib import Path

from utils.arguments import initialize_argparser
from utils.frame_editor import FrameEditor
from utils.disparity_to_dets import DisparityToDetections
from utils.annotation_node import AnnotationNode

from depthai_nodes.node import ApplyColormap

_, args = initialize_argparser()

PATH = (Path(__file__).parent / "resources").resolve().absolute()
SIZE = (1280, 800)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    pipeline.setCalibrationData(dai.CalibrationHandler(str(PATH / "calib.json")))

    left = pipeline.create(dai.node.ReplayVideo)
    left.setReplayVideoFile(PATH / "left.mp4")
    left.setOutFrameType(dai.ImgFrame.Type.RAW8)
    left.setSize(SIZE)

    right = pipeline.create(dai.node.ReplayVideo)
    right.setReplayVideoFile(PATH / "right.mp4")
    right.setOutFrameType(dai.ImgFrame.Type.RAW8)
    right.setSize(SIZE)

    left_frame_editor = pipeline.create(FrameEditor, dai.CameraBoardSocket.CAM_B)
    right_frame_editor = pipeline.create(FrameEditor, dai.CameraBoardSocket.CAM_C)

    left.out.link(left_frame_editor.input)
    right.out.link(right_frame_editor.input)

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_frame_editor.output, right=right_frame_editor.output
    )

    stereo.initialConfig.setMedianFilter(dai.StereoDepthConfig.MedianFilter.KERNEL_7x7)
    stereo.setLeftRightCheck(True)
    stereo.setSubpixel(False)

    detection_generator = pipeline.create(DisparityToDetections).build(
        disparity=stereo.disparity,
        max_disparity=stereo.initialConfig.getMaxDisparity(),
        roi=(50, 50, 550, 350),
    )

    # object tracking
    objectTracker = pipeline.create(dai.node.ObjectTracker)
    objectTracker.setTrackerType(dai.TrackerType.ZERO_TERM_COLOR_HISTOGRAM)
    objectTracker.setTrackerIdAssignmentPolicy(
        dai.TrackerIdAssignmentPolicy.SMALLEST_ID
    )

    color_transform_disparity = pipeline.create(ApplyColormap).build(stereo.disparity)
    color_transform_disparity.out.link(objectTracker.inputTrackerFrame)
    color_transform_disparity.out.link(objectTracker.inputDetectionFrame)
    detection_generator.out.link(objectTracker.inputDetections)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        objectTracker.out, axis=args.axis, roi_position=args.roi_position
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
