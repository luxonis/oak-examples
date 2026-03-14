import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
from utils.arguments import initialize_argparser
from utils.stereo_config_controller import StereoConfigController

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    preview = cam.requestOutput(
        size=(640, 480), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    left_out = left.requestOutput(
        size=(640, 480), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    right_out = right.requestOutput(
        size=(640, 480), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    stereo = pipeline.create(dai.node.StereoDepth).build(left=left_out, right=right_out)
    stereo.setRuntimeModeSwitch(True)
    stereo.initialConfig.setLeftRightCheck(True)
    stereo.initialConfig.setConfidenceThreshold(15)
    stereo.initialConfig.setSubpixelFractionalBits(3)
    stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)

    stereo_controller = pipeline.create(StereoConfigController).build(preview=preview)
    stereo_controller.out_cfg.link(stereo.inputConfig)

    depth_color = pipeline.create(ApplyDepthColormap).build(stereo.disparity)
    depth_color.setColormap(cv2.COLORMAP_JET)

    sync = pipeline.create(dai.node.Sync)
    depth_color.out.link(sync.inputs["disparity"])
    preview.link(sync.inputs["preview"])

    demux = pipeline.create(dai.node.MessageDemux)
    sync.out.link(demux.input)

    visualizer.addTopic("Color", demux.outputs["preview"], "color")
    visualizer.addTopic("Depth", demux.outputs["disparity"], "depth")
    visualizer.addTopic("Stereo config", stereo_controller.out_annotations, "color")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        else:
            stereo_controller.handle_key_press(key)
