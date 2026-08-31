import argparse as argparse
import asyncio
import math
import time

import depthai as dai
from foxglove_websocket import run_cancellable
from foxglove_websocket.server import FoxgloveServer
from utils.arguments import initialize_argparser
from utils.foxglove_utils import (
    Listener,
    create_channels,
    process_pointcloud,
    send_frame,
    send_pointcloud,
)

_, args = initialize_argparser()

resolution = (640, 400)

# To speed up visualization downsample the pointcloud before operating on it and visualizing
downsample_pcl = True


async def main():
    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        color_q = None
        left_q = None
        right_q = None
        pcl_q = None
        if not args.no_color:
            color_cam = pipeline.create(dai.node.Camera).build(
                dai.CameraBoardSocket.CAM_A
            )
            color_out = color_cam.requestOutput(
                resolution, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
            )
            color_q = color_out.createOutputQueue(blocking=False, maxSize=1)

        if args.left:
            left_cam = pipeline.create(dai.node.Camera).build(
                dai.CameraBoardSocket.CAM_B
            )
            left_out = left_cam.requestOutput(
                resolution, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
            )

            if args.left:
                left_q = left_out.createOutputQueue(blocking=False, maxSize=1)

        if args.right:
            right_cam = pipeline.create(dai.node.Camera).build(
                dai.CameraBoardSocket.CAM_C
            )
            right_out = right_cam.requestOutput(
                resolution, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
            )

            if args.right:
                right_q = right_out.createOutputQueue(blocking=False, maxSize=1)

        if args.pointcloud:
            depth = pipeline.create(dai.node.Depth)
            depth.build(
                dai.node.Depth.Algorithm.AUTO, fps=args.fps_limit, size=resolution
            )

            if not args.no_color:
                depth.setAlignTo(color_out)
                depth_out = depth.depth
            else:
                depth_out = depth.depth

            point_cloud = pipeline.create(dai.node.PointCloud)
            depth_out.link(point_cloud.inputDepth)
            pcl_q = point_cloud.outputPointCloud.createOutputQueue(
                blocking=False, maxSize=8
            )
        else:
            pcl_q = None

        print("Pipeline created.")
        pipeline.start()

        # Start server and wait for foxglove connection
        async with FoxgloveServer("0.0.0.0", 8765, "DepthAI server") as server:
            server.set_listener(Listener())

            (
                color_channel,
                pointcloud_channel,
                left_channel,
                right_channel,
            ) = await create_channels(
                server, not args.no_color, args.pointcloud, args.left, args.right
            )

            while pipeline.isRunning():
                tmpTime = time.time_ns()
                sec = math.trunc(tmpTime / 1e9)
                nsec = tmpTime - sec

                await asyncio.sleep(0.01)

                if color_q is not None and color_q.has():
                    frame = color_q.get().getCvFrame()
                    await send_frame(server, frame, sec, nsec, color_channel)
                if left_q is not None and left_q.has():
                    frame = left_q.get().getCvFrame()
                    await send_frame(server, frame, sec, nsec, left_channel)
                if right_q is not None and right_q.has():
                    frame = right_q.get().getCvFrame()
                    await send_frame(server, frame, sec, nsec, right_channel)
                if pcl_q is not None and pcl_q.has():
                    pcl_data = pcl_q.get()
                    pcl_processed = process_pointcloud(
                        pcl_data.getPoints(), downsample_pcl
                    )
                    await send_pointcloud(
                        server, pcl_processed, sec, nsec, pointcloud_channel
                    )


if __name__ == "__main__":
    run_cancellable(main())
