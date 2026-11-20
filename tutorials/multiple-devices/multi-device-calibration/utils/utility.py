from typing import List, Optional

import depthai as dai


def select_devices(
    devices: List[str],
    include_ip: bool = False,
    max_devices: Optional[int] = None,
) -> List[dai.DeviceInfo]:
    """Return the devices named on the command line, or discover them.

    Discovery skips IP-only devices (e.g. OAK-4) unless include_ip is set, so a
    shared network full of cameras is not opened by accident.
    """
    if devices:
        return [dai.DeviceInfo(device) for device in devices]

    infos = dai.Device.getAllAvailableDevices()
    if not include_ip:
        infos = [
            info for info in infos if info.protocol != dai.XLinkProtocol.X_LINK_TCP_IP
        ]
    if max_devices is not None and len(infos) > max_devices:
        print(f"Using the first {max_devices} of {len(infos)} discovered devices.")
        infos = infos[:max_devices]
    return infos
