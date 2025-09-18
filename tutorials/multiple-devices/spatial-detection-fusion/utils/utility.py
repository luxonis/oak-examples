import numpy as np
import os
import depthai as dai
from typing import List, Optional, Callable, Dict, Any


def filter_devices(
    devices: List[dai.DeviceInfo],
    include_ip: bool = False,
    max_devices: Optional[int] = None,
    warn_if_many_ip: Optional[int] = 5,
) -> List[dai.DeviceInfo]:
    """
    Args:
        devices: list of all DeviceInfo from dai.Device.getAllAvailableDevices()
        include_ip: if False, drop all TCP_IP attachments (e.g. OAK-4). If True, keep them.
        max_devices: if set, only return up to this many devices (first-come).
        warn_if_many_ip: if include_ip and the count of IP devices >= this, emit a warning.
    """
    internal, ip_only = [], []
    for d in devices:
        if d.protocol == dai.XLinkProtocol.X_LINK_TCP_IP:
            ip_only.append(d)
        else:
            internal.append(d)

    if include_ip:
        result = internal + ip_only
        if warn_if_many_ip and len(ip_only) >= warn_if_many_ip:
            print(
                f"⚠️  Warning: {len(ip_only)} IP-only devices detected. You may saturate your network."
            )
    else:
        result = internal

    if max_devices is not None and len(result) > max_devices:
        print(f"⚠️  Capping device list to first {max_devices} of {len(result)} total.")
        result = result[:max_devices]

    return result


def setup_devices(
    devices_info: List[dai.DeviceInfo],
    visualizer: dai.RemoteConnection,
    pipeline_builder: Callable[
        [dai.DeviceInfo, dai.RemoteConnection], Optional[Dict[str, Any]]
    ],
) -> List[Dict[str, Any]]:
    initialized_setups: List[Dict[str, Any]] = []
    for dev_info in devices_info:
        setup_info = pipeline_builder(dev_info, visualizer)
        if setup_info:
            initialized_setups.append(setup_info)
        else:
            print(
                f"--- Failed to set up device {dev_info.getDeviceId()}. Skipping. ---"
            )
    return initialized_setups


def start_pipelines(
    setups: List[Dict[str, Any]], visualizer: dai.RemoteConnection
) -> List[Dict[str, Any]]:
    active_pipelines_info: List[Dict[str, Any]] = []
    for setup in setups:
        try:
            print(f"\nStarting pipeline for device {setup['mxid']}...")
            setup["pipeline"].start()

            visualizer.registerPipeline(setup["pipeline"])
            print(f"Pipeline for {setup['mxid']} registered with visualizer.")
            active_pipelines_info.append(setup)
        except Exception as e:
            print(
                f"Error starting or registering pipeline for device {setup['mxid']}: {e}"
            )
            setup["device"].close()
            continue
    return active_pipelines_info


def any_pipeline_running(pipelines: List[Dict[str, Any]]) -> bool:
    """Return True if at least one pipeline is still running."""
    return any(item["pipeline"].isRunning() for item in pipelines)


def load_extrinsics_for_devices(
    devices_info: List[dai.DeviceInfo], cal_dir: str
) -> Dict[str, Dict[str, Any]]:
    """Loads extrinsic calibration data and assigns a friendly ID for each device."""
    all_extrinsics: Dict[str, Dict[str, Any]] = {}
    for friendly_id_counter, dev_info in enumerate(devices_info):
        mxid = dev_info.getDeviceId()
        file_path = os.path.join(cal_dir, f"extrinsics_{mxid}.npz")
        if os.path.exists(file_path):
            try:
                data = np.load(file_path)
                if "cam_to_world" in data:
                    friendly_id = friendly_id_counter + 1
                    all_extrinsics[mxid] = {
                        "cam_to_world": data["cam_to_world"],
                        "friendly_id": friendly_id,
                    }
                    print(
                        f"✅ Loaded extrinsics for {mxid} (Friendly ID: {friendly_id_counter + 1})"
                    )
                else:
                    print(
                        f"⚠️ Extrinsics file for {mxid} is missing 'cam_to_world' key."
                    )
            except Exception as e:
                print(f"❌ Error loading extrinsics for {mxid}: {e}")
        else:
            print(
                f"⚠️ Extrinsics file not found for {mxid} at {file_path}. This device will be skipped."
            )
    return all_extrinsics
