import logging
from typing import Callable, List, Optional

import depthai as dai

logger = logging.getLogger(__name__)

HTTP_PORT = 8082


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
        logger.info(
            f"Using the first {max_devices} of {len(infos)} discovered devices."
        )
        infos = infos[:max_devices]
    return infos


def run_multi_device_pipeline(
    device_infos: List[dai.DeviceInfo],
    setup_device: Callable[[dai.Pipeline, dai.Device, dai.RemoteConnection], None],
) -> None:
    """Build ONE pipeline that spans all devices and run it until 'q' is pressed.

    setup_device creates the nodes of a single device; it is called once per device.
    """
    if not device_infos:
        logger.error("No DepthAI devices found.")
        return
    logger.info(f"Found {len(device_infos)} DepthAI devices to configure.")

    # No implicit device: devices are added explicitly and nodes are created on them.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

        for info in device_infos:
            device = pipeline.addDevice(info)
            logger.info(f"=== Connected to device: {device.getDeviceId()}")
            logger.info(
                f"    >>> Cameras: {[c.name for c in device.getConnectedCameras()]}"
            )
            logger.info(f"    >>> USB speed: {device.getUsbSpeed().name}")
            setup_device(pipeline, device, visualizer)

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        logger.info(f"Pipeline started with {len(device_infos)} device(s).")

        while pipeline.isRunning():
            pipeline.processTasks()
            key = visualizer.waitKey(1)
            if key == ord("q"):
                logger.info("Got 'q' key from the remote connection! Shutting down.")
                break
