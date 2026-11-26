"""Preview the color camera of every device from a single multi-device pipeline."""

import logging
import depthai as dai

from utils.arguments import initialize_argparser
from utils.utility import run_multi_device_pipeline, select_devices

logging.basicConfig(level=logging.INFO, format="%(message)s")


def setup_preview(
    pipeline: dai.Pipeline, device: dai.Device, visualizer: dai.RemoteConnection
) -> None:
    # Passing the device to create() places the node on that device.
    cam_preview = (
        pipeline.create(dai.node.Camera, device)
        .build(dai.CameraBoardSocket.CAM_A)
        .requestOutput((640, 400), dai.ImgFrame.Type.NV12)
    )

    visualizer.addTopic(f"RGB - {device.getDeviceId()}", cam_preview)


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    run_multi_device_pipeline(device_infos, setup_preview)


if __name__ == "__main__":
    main()
