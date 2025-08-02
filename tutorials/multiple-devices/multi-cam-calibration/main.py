import os
import depthai as dai
from typing import List, Optional, Dict, Any
import numpy as np
from utils.utility import (
    filter_devices,
    setup_devices,
    start_pipelines,
    any_pipeline_running,
)
from utils.arguments import initialize_argparser
from utils.calibration_node import CalibrationNode


_, args = initialize_argparser()

HTTP_PORT = 8082
STILL_WIDTH, STILL_HEIGHT = 3840, 2160  # 4K UHD


def setup_device_pipeline(
    dev_info: dai.DeviceInfo, visualizer: dai.RemoteConnection
) -> Optional[Dict[str, Any]]:
    mxid = dev_info.getDeviceId()
    print(f"\nAttempting to connect to device: {mxid}...")
    device_instance = dai.Device(dev_info)

    print(f"=== Successfully connected to device: {mxid}")

    cameras = device_instance.getConnectedCameraFeatures()
    print(f"    >>> Cameras: {[c.socket.name for c in cameras]}")
    print(f"    >>> USB speed: {device_instance.getUsbSpeed().name}")

    pipeline = dai.Pipeline(device_instance)
    print(f"    Pipeline created for device: {mxid}")

    preview_width, preview_height = (640, 400)
    cam_socket = dai.CameraBoardSocket.CAM_A
    camera_object = pipeline.create(dai.node.Camera).build(cam_socket)
    cam_preview = camera_object.requestOutput(
        (preview_width, preview_height), dai.ImgFrame.Type.NV12
    )
    cam_high_res = camera_object.requestOutput(
        (STILL_WIDTH, STILL_HEIGHT), dai.ImgFrame.Type.NV12
    )

    calib_data = device_instance.readCalibration()
    intrinsic_mat_still = np.array(
        calib_data.getCameraIntrinsics(cam_socket, STILL_WIDTH, STILL_HEIGHT)
    )

    control_q = camera_object.inputControl.createInputQueue()
    still_q = cam_high_res.createOutputQueue(maxSize=2, blocking=False)

    calibration_node = pipeline.create(CalibrationNode).build(
        preview_input=cam_preview,
        intrinsic_mat_still=intrinsic_mat_still,
        device=device_instance,
        preview_width=preview_width,
        preview_height=preview_height,
        still_width=STILL_WIDTH,
        still_height=STILL_HEIGHT,
        control_q=control_q,
        still_q=still_q,
    )

    visualizer.addTopic(f"{mxid}", cam_preview)
    visualizer.addTopic(
        f"{mxid} calibration annotations", calibration_node.annotation_out
    )

    print(f"    Pipeline for {mxid} configured. Ready to be started.")
    return {
        "device": device_instance,
        "pipeline": pipeline,
        "mxid": mxid,
        "calibration_node": calibration_node,
    }


def main():
    all_device_infos = dai.Device.getAllAvailableDevices()
    available_devices_info = filter_devices(
        all_device_infos,
        include_ip=args.include_ip,
        max_devices=args.max_devices,
    )

    if not available_devices_info:
        print("No DepthAI devices found.")
        return

    print(f"Found {len(available_devices_info)} DepthAI devices to configure.")

    visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

    initialized_setups: List[Dict[str, Any]] = setup_devices(
        available_devices_info, visualizer, setup_device_pipeline
    )
    if not initialized_setups:
        print("No devices were successfully set up. Exiting.")
        return

    active_pipelines_info: List[Dict[str, Any]] = start_pipelines(
        initialized_setups, visualizer
    )
    print(f"\n{len(active_pipelines_info)} device(s) should be streaming.")

    current_idx = 0
    if active_pipelines_info:
        # Initially select the first camera for calibration
        active_pipelines_info[current_idx]["calibration_node"].calib = True

    while any_pipeline_running(active_pipelines_info):
        key = visualizer.waitKey(1)

        if not active_pipelines_info:  # If all pipelines stopped or failed
            print("No active pipelines. Exiting loop.")
            break

        if key == ord("q"):
            print("Got 'q' key from the remote connection! Shutting down.")
            for setup in active_pipelines_info:
                if setup.get("device"):
                    setup["device"].close()
            os._exit(0)

        elif key == ord("a"):
            active_pipelines_info[current_idx]["calibration_node"].calib = False
            current_idx = (current_idx + 1) % len(
                active_pipelines_info
            )  # Cycle through cameras
            active_pipelines_info[current_idx]["calibration_node"].calib = True
            print(
                f"INFO: Switched calibration focus to device {active_pipelines_info[current_idx]['mxid']}"
            )

        elif key == ord("c"):
            if not active_pipelines_info:
                continue
            current_setup = active_pipelines_info[current_idx]

            print(
                f"INFO: 'c' pressed. Asking CalibrationNode to capture and calibrate for {current_setup['mxid']}..."
            )

            calibration_successful = current_setup[
                "calibration_node"
            ].capture_and_calibrate()

            if calibration_successful:
                print(
                    f"[{current_setup['mxid']}] Main: Calibration process reported success."
                )
            else:
                print(
                    f"[{current_setup['mxid']}] Main: Calibration process reported failure or was skipped."
                )

    print("INFO: Main loop finished. Cleaning up...")
    for setup in active_pipelines_info:
        if setup.get("device"):
            try:
                setup["device"].close()
            except Exception as e:
                print(f"Error closing device {setup.get('mxid', 'N/A')}: {e}")


if __name__ == "__main__":
    main()
