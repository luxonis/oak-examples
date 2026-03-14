import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
import numpy as np
import cv2

from utils.arguments import initialize_argparser
from utils.point_tracker import PointTracker


_, args = initialize_argparser()

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

platform = device.getPlatformAsString()

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

if args.fps_limit is None:
    args.fps_limit = 15
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

FRAME_WIDTH = 640
FRAME_HEIGHT = 400

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    cam = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )
    cam_out = cam.requestOutput(
        size=(FRAME_WIDTH, FRAME_HEIGHT),
        type=dai.ImgFrame.Type.RGB888i,
        fps=args.fps_limit,
    )

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    left_out = left.requestOutput(
        (FRAME_WIDTH, FRAME_HEIGHT), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    right_out = right.requestOutput(
        (FRAME_WIDTH, FRAME_HEIGHT), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_out,
        right=right_out,
        presetMode=dai.node.StereoDepth.PresetMode.FAST_DENSITY,
    )

    align = pipeline.create(dai.node.ImageAlign)
    stereo.depth.link(align.input)
    cam_out.link(align.inputAlignTo)

    coloredDepth = pipeline.create(ApplyDepthColormap).build(align.outputAligned)
    coloredDepth.setColormap(cv2.COLORMAP_JET)

    point_tracker = pipeline.create(
        PointTracker, frame_width=FRAME_WIDTH, frame_height=FRAME_HEIGHT
    ).build(cam_out, align.outputAligned)
    calibration_data = device.readCalibration()
    camera_matrix = np.array(
        calibration_data.getCameraIntrinsics(
            dai.CameraBoardSocket.CAM_A, FRAME_WIDTH, FRAME_HEIGHT
        )
    )

    point_tracker.set_camera_matrix(camera_matrix)

    def point_selection_service(clicks: dict):
        if clicks.get("clear"):
            point_tracker.clear_points()
            return {"ok": True, "cleared": True, "point_count": 0}

        try:
            x = float(clicks["x"])
            y = float(clicks["y"])
        except Exception as e:
            return {"ok": False, "error": f"bad payload: {e}"}

        point_tracker.add_point(x, y, FRAME_WIDTH, FRAME_HEIGHT)
        return {"ok": True}

    def clear_points_service(data: dict):
        point_tracker.clear_points()
        return {"ok": True, "cleared": True}

    def get_distance_service(data: dict):
        distance_data = point_tracker.get_latest_distance()
        return {"ok": True, **distance_data}

    def toggle_tracking_service(data: dict):
        """Toggle tracking mode on/off"""
        current_mode = point_tracker.mode["name"]
        if current_mode == "tracking":
            point_tracker.set_mode(3)  # Switch to static mode
            new_mode = "static"
        else:
            point_tracker.set_mode(1)  # Switch to tracking mode
            new_mode = "tracking"

        return {
            "ok": True,
            "mode": new_mode,
            "tracking_enabled": new_mode == "tracking",
        }

    def get_tracking_status_service(data: dict):
        """Get current tracking status"""
        return {
            "ok": True,
            "mode": point_tracker.mode["name"],
            "tracking_enabled": point_tracker.mode["name"] == "tracking",
        }

    visualizer.registerService("Selection Service", point_selection_service)
    visualizer.registerService("Clear Points Service", clear_points_service)
    visualizer.registerService("Get Distance Service", get_distance_service)
    visualizer.registerService("Toggle Tracking Service", toggle_tracking_service)
    visualizer.registerService(
        "Get Tracking Status Service", get_tracking_status_service
    )

    visualizer.addTopic("Video", cam_out, "images")
    visualizer.addTopic("Depth", coloredDepth.out, "images")
    visualizer.addTopic("Point Annotations", point_tracker.output_annotations, "images")

    pipeline.start()
    print("Pipeline started successfully")

    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
