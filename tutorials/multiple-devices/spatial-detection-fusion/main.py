import os
import depthai as dai
from typing import List, Optional, Dict, Any

from utils.utility import (
    filter_devices,
    setup_devices,
    start_pipelines,
    any_pipeline_running,
    load_extrinsics_for_devices,
)
import utils.config as config
from utils.arguments import initialize_argparser
from utils.birds_eye_view import BirdsEyeView
from utils.fusion import FusionManager
from utils import config as app_config
from functools import partial

_, args = initialize_argparser()


def setup_device_pipeline(
    dev_info: dai.DeviceInfo,
    visualizer: dai.RemoteConnection,
    fusion_manager: FusionManager,
    main_device: dai.Device,
    main_pipeline: Optional[dai.Pipeline] = None,
    fps_limit: int = 30,
) -> Optional[Dict[str, Any]]:
    """Sets up pipeline for a single device for BEV application."""
    mxid = dev_info.getDeviceId()
    if mxid == main_device.getDeviceId():
        print(
            f"\nSkipping initialization of device {mxid} as it is already initialized."
        )
        device_instance = main_device
        pipeline = main_pipeline if main_pipeline else dai.Pipeline(device_instance)
    else:
        try:
            print(f"\nAttempting to connect to device: {mxid}...")
            device_instance = dai.Device(dev_info)
            print(f"=== Successfully connected to device: {mxid}")
            pipeline = dai.Pipeline(device_instance)
            print(f"    >>> Pipeline created for device: {mxid}")
        except RuntimeError as e:
            print(f"    ERROR: Failed to connect to device {mxid}: {e}")
            return None

    cameras = device_instance.getConnectedCameraFeatures()
    print(f"    >>> Cameras: {[c.socket.name for c in cameras]}")
    print(f"    >>> USB speed: {device_instance.getUsbSpeed().name}")

    platform = device_instance.getPlatformAsString()
    model_description = dai.NNModelDescription(
        app_config.NN_MODEL_SLUG, platform=platform
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    nn_input_size = nn_archive.getInputSize()
    if not nn_input_size:
        print(
            f"    ERROR: No input size found in NN archive for {mxid}. Skipping device setup."
        )
        return None

    cam = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_A, sensorFps=fps_limit
    )

    left_cam = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B,
    )
    right_cam = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C,
    )
    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_cam.requestOutput(nn_input_size, fps=fps_limit),
        right=right_cam.requestOutput(nn_input_size, fps=fps_limit),
        presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
    )
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

    if platform == "RVC2":
        stereo.setOutputSize(*nn_input_size)
    stereo.setLeftRightCheck(True)
    stereo.setRectification(True)

    detector = pipeline.create(dai.node.SpatialDetectionNetwork).build(
        input=cam, stereo=stereo, nnArchive=nn_archive
    )
    detector.setBoundingBoxScaleFactor(0.2)

    if platform == "RVC2":
        detector.setNNArchive(nn_archive, numShaves=7)

    detector.out.link(fusion_manager.inputs[mxid])

    visualizer.addTopic(f"{mxid}", detector.passthrough, group=mxid)
    visualizer.addTopic(f"{mxid} Detections", detector.out, group=mxid)

    print(f"        Pipeline for {mxid} configured. Ready to be started.")
    return {
        "device": device_instance,
        "pipeline": pipeline,
        "mxid": mxid,
    }


def main():
    all_device_infos = dai.Device.getAllAvailableDevices()
    available_devices_info = filter_devices(
        all_device_infos, include_ip=args.include_ip, max_devices=args.max_devices
    )

    if not available_devices_info:
        print("No DepthAI devices found.")
        return

    print(f"Found {len(available_devices_info)} DepthAI devices to configure.")

    all_cam_extrinsics = load_extrinsics_for_devices(
        available_devices_info, config.CALIBRATION_DATA_DIR
    )
    if not all_cam_extrinsics:
        print("No extrinsic calibrations loaded. BEV cannot function. Exiting.")
        return

    devices_to_setup_info = [
        dev for dev in available_devices_info if dev.getDeviceId() in all_cam_extrinsics
    ]
    print(f"Proceeding with {len(devices_to_setup_info)} devices that have extrinsics.")

    visualizer = dai.RemoteConnection(httpPort=app_config.HTTP_PORT)

    main_device = dai.Device(devices_to_setup_info[0])
    print(
        f"\nSuccessfully connected to device {main_device.getDeviceId()} for main pipeline."
    )
    pipeline = dai.Pipeline(main_device)
    fusion_manager = pipeline.create(
        FusionManager,
        all_cam_extrinsics,
        args.fps_limit,
        app_config.DISTANCE_THRESHOLD_M,
    )

    configured_pipeline_builder = partial(
        setup_device_pipeline,
        fusion_manager=fusion_manager,
        main_device=main_device,
        main_pipeline=pipeline,
        fps_limit=args.fps_limit,
    )
    initialized_setups: List[Dict[str, Any]] = setup_devices(
        available_devices_info, visualizer, configured_pipeline_builder
    )
    if not initialized_setups:
        print("No devices were successfully set up. Exiting.")
        return

    bev = pipeline.create(BirdsEyeView).build(
        all_cam_extrinsics=all_cam_extrinsics, detections=fusion_manager.output
    )

    visualizer.addTopic("BEV Canvas", bev.canvas, group="BEV")
    visualizer.addTopic("BEV Cameras", bev.cameras_pos, group="BEV")
    visualizer.addTopic("BEV History Trails", bev.history_trails, group="BEV")
    visualizer.addTopic("BEV Detections", bev.detections, group="BEV")

    active_device_pipelines_info: List[Dict[str, Any]] = start_pipelines(
        initialized_setups, visualizer
    )
    if not active_device_pipelines_info:
        print("No device pipelines are active. Exiting.")
        return
    print(f"\n{len(active_device_pipelines_info)} device pipeline(s) started.")

    while any_pipeline_running(active_device_pipelines_info):
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got 'q' key from the remote connection! Shutting down.")
            os._exit(0)


if __name__ == "__main__":
    main()
