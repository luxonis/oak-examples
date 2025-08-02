import os
import depthai as dai
from typing import List, Optional, Dict, Any

from utils.utility import (
    filter_devices,
    setup_devices,
    start_pipelines,
    any_pipeline_running,
)
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

HTTP_PORT = 8082


def setup_mjpeg_pipeline(
    dev_info: dai.DeviceInfo, visualizer: dai.RemoteConnection
) -> Optional[Dict[str, Any]]:
    mxid = dev_info.getDeviceId()
    print(f"\nAttempting to connect to device for MJPEG streaming: {mxid}...")
    device_instance = None

    device_instance = dai.Device(dev_info)
    print(f"=== Successfully connected to device: {mxid}")

    cameras_features = device_instance.getConnectedCameraFeatures()
    print(f"    >>> Cameras: {[c.socket.name for c in cameras_features]}")
    print(f"    >>> USB speed: {device_instance.getUsbSpeed().name}")

    pipeline = dai.Pipeline(device_instance)
    print(f"    Pipeline created for device: {mxid}")

    cam_rgb = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    rgb_video_out = cam_rgb.requestOutput(
        size=(1920, 1080), fps=30, type=dai.ImgFrame.Type.NV12
    )

    video_encoder = pipeline.create(dai.node.VideoEncoder).build(
        input=rgb_video_out,
        frameRate=30,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    visualizer.addTopic(
        topicName=f"H264 Stream - {mxid}",
        output=video_encoder.out,
    )
    print(
        f"    Pipeline for MJPEG streaming on {mxid} configured. Ready to be started."
    )
    return {"device": device_instance, "pipeline": pipeline, "mxid": mxid}


def main():
    all_device_infos = dai.Device.getAllAvailableDevices()
    available_devices_info = filter_devices(
        all_device_infos,
        include_ip=args.include_ip,
        max_devices=args.max_devices,
    )

    if not available_devices_info:
        print("No DepthAI devices found or filtered out.")
        return

    print(f"Found {len(available_devices_info)} DepthAI devices to configure.")

    visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

    initialized_setups: List[Dict[str, Any]] = setup_devices(
        available_devices_info, visualizer, setup_mjpeg_pipeline
    )
    if not initialized_setups:
        print("No devices were successfully set up. Exiting.")
        return

    active_pipelines_info: List[Dict[str, Any]] = start_pipelines(
        initialized_setups, visualizer
    )
    print(f"\n{len(active_pipelines_info)} device(s) should be streaming.")

    while any_pipeline_running(active_pipelines_info):
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got 'q' key from the remote connection! Shutting down.")
            os._exit(0)


if __name__ == "__main__":
    main()
