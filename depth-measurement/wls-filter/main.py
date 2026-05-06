import cv2
import depthai as dai
from utils.host_wls_filter import WLSFilter
from depthai_nodes.node import ApplyDepthColormap
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

LR_CHECK = False  # Better handling for occlusions

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    left_out = left.requestOutput(size=(640, 400), type=dai.ImgFrame.Type.NV12)

    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    right_out = right.requestOutput(size=(640, 400), type=dai.ImgFrame.Type.NV12)

    stereo = pipeline.create(dai.node.StereoDepth).build(left=left_out, right=right_out)
    stereo.initialConfig.setConfidenceThreshold(255)
    stereo.initialConfig.setMedianFilter(dai.StereoDepthConfig.MedianFilter.KERNEL_5x5)
    stereo.setRectifyEdgeFillColor(
        0
    )  # Black, to better see the cutout from rectification (black stripe on the edges)
    stereo.setLeftRightCheck(LR_CHECK)
    stereo.setSubpixel(False)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_C)

    calib = device.readCalibration()
    baseline = calib.getBaselineDistance()
    wls_filter = pipeline.create(WLSFilter).build(
        disparity=stereo.disparity,
        rectified_right=stereo.rectifiedRight,
        max_disparity=stereo.initialConfig.getMaxDisparity(),
        baseline=baseline,
    )

    disp_colored = pipeline.create(ApplyDepthColormap).build(stereo.disparity)
    disp_colored.setColormap(cv2.COLORMAP_JET)

    filtered_disp_colored = pipeline.create(ApplyDepthColormap).build(
        wls_filter.filtered_disp
    )
    filtered_disp_colored.setColormap(cv2.COLORMAP_JET)

    visualizer.addTopic("Rectified Right", stereo.rectifiedRight)
    visualizer.addTopic("Disparity", disp_colored.out)
    visualizer.addTopic("WLS Raw Depth", wls_filter.depth_frame)
    visualizer.addTopic("WLS Filtered Disparity", wls_filter.filtered_disp)
    visualizer.addTopic("WLS Colored Disparity", filtered_disp_colored.out)
    visualizer.addTopic("WLS Annotations", wls_filter.annotations)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        else:
            wls_filter.handle_key(key)
