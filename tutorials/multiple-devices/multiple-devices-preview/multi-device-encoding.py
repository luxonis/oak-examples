"""Stream H.264 video from every device of a single multi-device pipeline."""

import depthai as dai

from utils.arguments import initialize_argparser
from utils.utility import run_multi_device_pipeline, select_devices


def setup_h264_stream(
    pipeline: dai.Pipeline, device: dai.Device, visualizer: dai.RemoteConnection
) -> None:
    # Camera and encoder both run on this device; only the encoded stream reaches the host.
    cam_rgb = pipeline.create(dai.node.Camera, device).build(
        dai.CameraBoardSocket.CAM_A
    )
    rgb_video_out = cam_rgb.requestOutput(
        size=(1920, 1080), fps=30, type=dai.ImgFrame.Type.NV12
    )

    video_encoder = pipeline.create(dai.node.VideoEncoder, device).build(
        input=rgb_video_out,
        frameRate=30,
        profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    visualizer.addTopic(
        topicName=f"H264 Stream - {device.getDeviceId()}",
        output=video_encoder.out,
    )


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    run_multi_device_pipeline(device_infos, setup_h264_stream)


if __name__ == "__main__":
    main()
