"""Run YOLOv6 Nano on every device of a single multi-device pipeline."""

import depthai as dai

from utils.arguments import initialize_argparser
from utils.utility import run_multi_device_pipeline, select_devices

MODEL = "luxonis/yolov6-nano:r2-coco-512x288"


def setup_detection(
    pipeline: dai.Pipeline, device: dai.Device, visualizer: dai.RemoteConnection
) -> None:
    device_id = device.getDeviceId()
    cam_node = pipeline.create(dai.node.Camera, device).build(
        dai.CameraBoardSocket.CAM_A
    )

    # Each device gets the model build for its own platform and runs inference itself.
    model_description = dai.NNModelDescription(
        MODEL, platform=device.getPlatformAsString()
    )
    detector = pipeline.create(dai.node.DetectionNetwork, device).build(
        cam_node, model_description
    )

    visualizer.addTopic(
        topicName=f"Video - {device_id}",
        output=detector.passthrough,
        group=device_id,
    )
    visualizer.addTopic(
        topicName=f"Detections - {device_id}",
        output=detector.out,
        group=device_id,
    )


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    run_multi_device_pipeline(device_infos, setup_detection)


if __name__ == "__main__":
    main()
