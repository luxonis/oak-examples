import base64
import json
import time
from datetime import timedelta
from typing import Tuple

import cv2
import depthai as dai
import numpy as np
import open3d as o3d
from foxglove_websocket.server import FoxgloveServer, FoxgloveServerListener
from foxglove_websocket.types import ChannelId


def _timedelta_ns(value: timedelta) -> int:
    return value // timedelta(microseconds=1) * 1_000


def host_clock_to_unix_offset_ns() -> int:
    """Offset that converts DepthAI host-clock timestamps to Unix time.

    ``Buffer.getTimestamp()`` is the capture time on the host steady clock that
    ``dai.Clock.now()`` reads, not wall-clock time.
    """
    return time.time_ns() - _timedelta_ns(dai.Clock.now())


def capture_stamp(msg: dai.Buffer, offset_ns: int) -> Tuple[int, int]:
    """Return the message capture time as Unix ``(sec, nsec)`` for a ROS header."""
    stamp_ns = _timedelta_ns(msg.getTimestamp()) + offset_ns
    return divmod(stamp_ns, 1_000_000_000)


class Listener(FoxgloveServerListener):
    def on_subscribe(self, server: FoxgloveServer, channel_id: ChannelId):
        print("First client subscribed to", channel_id)

    def on_unsubscribe(self, server: FoxgloveServer, channel_id: ChannelId):
        print("Last client unsubscribed from", channel_id)


async def create_channels(server, color, pointcloud, left, right):
    # Create schema for the type of message that will be sent over to foxglove
    # for more details on how the schema must look like visit:
    # http://docs.ros.org/en/noetic/api/sensor_msgs/html/index-msg.html
    if color:
        color_channel = await server.add_channel(
            {
                "topic": "colorImage",
                "encoding": "json",
                "schemaName": "ros.sensor_msgs.CompressedImage",
                "schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "header": {
                                "type": "object",
                                "properties": {
                                    "stamp": {
                                        "type": "object",
                                        "properties": {
                                            "sec": {"type": "integer"},
                                            "nsec": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                            "format": {"type": "string"},
                            "data": {"type": "string", "contentEncoding": "base64"},
                        },
                    },
                ),
            }
        )
    else:
        color_channel = None

    if pointcloud:
        pointcloud_channel = await server.add_channel(
            {
                "topic": "pointCloud",
                "encoding": "json",
                "schemaName": "ros.sensor_msgs.PointCloud2",
                "schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "header": {
                                "type": "object",
                                "properties": {
                                    "seq": {"type": "integer"},
                                    "stamp": {
                                        "type": "object",
                                        "properties": {
                                            "sec": {"type": "integer"},
                                            "nsec": {"type": "integer"},
                                        },
                                    },
                                    "frame_id": {"type": "string"},
                                },
                            },
                            "height": {"type": "integer"},
                            "width": {"type": "integer"},
                            "fields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "offset": {"type": "integer"},
                                        "datatype": {"type": "integer"},
                                        "count": {"type": "integer"},
                                    },
                                },
                            },
                            "is_bigendian": {"type": "boolean"},
                            "point_step": {"type": "integer"},
                            "row_step": {"type": "integer"},
                            "data": {"type": "string", "contentEncoding": "base64"},
                            "is_dense": {"type": "boolean"},
                        },
                    },
                ),
            }
        )
    else:
        pointcloud_channel = None

    if left:
        left_channel = await server.add_channel(
            {
                "topic": "leftImage",
                "encoding": "json",
                "schemaName": "ros.sensor_msgs.CompressedImage",
                "schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "header": {
                                "type": "object",
                                "properties": {
                                    "stamp": {
                                        "type": "object",
                                        "properties": {
                                            "sec": {"type": "integer"},
                                            "nsec": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                            "format": {"type": "string"},
                            "data": {"type": "string", "contentEncoding": "base64"},
                        },
                    },
                ),
            }
        )
    else:
        left_channel = None

    if right:
        right_channel = await server.add_channel(
            {
                "topic": "rightImage",
                "encoding": "json",
                "schemaName": "ros.sensor_msgs.CompressedImage",
                "schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "header": {
                                "type": "object",
                                "properties": {
                                    "stamp": {
                                        "type": "object",
                                        "properties": {
                                            "sec": {"type": "integer"},
                                            "nsec": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                            "format": {"type": "string"},
                            "data": {"type": "string", "contentEncoding": "base64"},
                        },
                    },
                ),
            }
        )
    else:
        right_channel = None

    return color_channel, pointcloud_channel, left_channel, right_channel


async def send_frame(server, frame, sec, nsec, channel):
    is_success, im_buf_arr = cv2.imencode(".jpg", frame)

    # Read from .jpeg format to buffer of bytes
    byte_im = im_buf_arr.tobytes()

    # Data must be encoded in base64
    data = base64.b64encode(byte_im).decode("ascii")

    # Data is sent with json (data must be in above schema order)
    await server.send_message(
        channel,
        sec * 1_000_000_000 + nsec,
        json.dumps(
            {
                "header": {"stamp": {"sec": sec, "nsec": nsec}, "frame_id": "front"},
                "format": "jpeg",
                "data": data,
            }
        ).encode("utf8"),
    )


async def send_pointcloud(server, pcl_data, sec, nsec, channel):
    buf = np.asarray(pcl_data)[:, :3].astype(np.float32).tobytes()

    # Data needs to be encoded in base64
    data = base64.b64encode(buf).decode("ascii")

    # Data is sent with json (data must be in above schema order)
    await server.send_message(
        channel,
        sec * 1_000_000_000 + nsec,
        json.dumps(
            {
                "header": {
                    "stamp": {"sec": sec, "nsec": nsec},
                    "frame_id": "front",
                },
                "height": 1,
                "width": len(pcl_data),
                "fields": [
                    {"name": "x", "offset": 0, "datatype": 7, "count": 1},
                    {"name": "y", "offset": 4, "datatype": 7, "count": 1},
                    {"name": "z", "offset": 8, "datatype": 7, "count": 1},
                ],
                "is_bigendian": False,
                "point_step": 12,
                "row_step": 12 * len(pcl_data),
                "data": data,
                "is_dense": True,
            }
        ).encode("utf8"),
    )


def process_pointcloud(pcl_points, downsample_pcl):
    pts = pcl_points
    pts = pts / 1000.0
    pts[:, 0] = -pts[:, 0]
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    pcd.remove_non_finite_points()
    if downsample_pcl:
        pcd = pcd.voxel_down_sample(voxel_size=0.03)
    return pcd.points
