"""The obstacle path turns a point cloud and gravity into obstacles and a plane status."""

import time
import unittest
from datetime import timedelta

import depthai as dai
import numpy as np
from device_lookup import setUpModule, tearDownModule  # noqa: F401

from depthai_pipeline.pointcloud_object_detection.node.point_cloud_object_detection import (
    PointCloudObjectDetectionNode,
)
from settings.settings import SpatialZone

HFOV_DEG = 67.3
POINTCLOUD_SIZE = (320, 180)
FX = FY = (POINTCLOUD_SIZE[0] / 2) / np.tan(np.radians(HFOV_DEG / 2))
CX, CY = POINTCLOUD_SIZE[0] / 2, POINTCLOUD_SIZE[1] / 2
DANGER_ZONE = SpatialZone(distance_mm=2000, x_min_mm=-500, x_max_mm=500)
WARNING_ZONE = SpatialZone(distance_mm=3000, x_min_mm=-1000, x_max_mm=1000)

# A level camera this high above the floor; camera axes are x right, y down, z forward.
# Its lowest pixel row meets the floor about 1.3 m ahead.
CAMERA_HEIGHT_MM = 500.0
MAX_DEPTH_MM = 6000.0


def pixel_rays() -> np.ndarray:
    """One camera-frame ray per pixel of the organized cloud, row by row, with z = 1."""
    u, v = np.meshgrid(
        np.arange(POINTCLOUD_SIZE[0]) + 0.5, np.arange(POINTCLOUD_SIZE[1]) + 0.5
    )
    return np.column_stack(
        [((u - CX) / FX).ravel(), ((v - CY) / FY).ravel(), np.ones(u.size)]
    )


def floor_hits(rays: np.ndarray) -> np.ndarray:
    """Ray lengths to the floor, infinite for rays that miss it."""
    with np.errstate(divide="ignore"):
        t = np.where(rays[:, 1] > 0, CAMERA_HEIGHT_MM / rays[:, 1], np.inf)
    return t


def box_hits(rays: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Ray lengths to an axis-aligned box, infinite for rays that miss it."""
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = lower / rays
        t2 = upper / rays
    near = np.nanmax(np.minimum(t1, t2), axis=1)
    far = np.nanmin(np.maximum(t1, t2), axis=1)
    return np.where((near <= far) & (near > 0), near, np.inf)


def organized_cloud(t: np.ndarray, rays: np.ndarray) -> np.ndarray:
    """Points along the rays; misses and far hits read zero like missing depth."""
    points = rays * t[:, None]
    points[~np.isfinite(t) | (points[:, 2] > MAX_DEPTH_MM)] = 0
    return points.astype(np.float32)


def flat_floor() -> np.ndarray:
    rays = pixel_rays()
    return organized_cloud(floor_hits(rays), rays)


def box_on_floor(front_mm: float) -> np.ndarray:
    """Floor plus a 400 mm box standing on it, centred ahead, front face at ``front_mm``."""
    rays = pixel_rays()
    box = box_hits(
        rays,
        lower=np.array([-200.0, CAMERA_HEIGHT_MM - 400, front_mm]),
        upper=np.array([200.0, CAMERA_HEIGHT_MM, front_mm + 400]),
    )
    return organized_cloud(np.minimum(floor_hits(rays), box), rays)


def wall_only() -> np.ndarray:
    """A wall facing the camera fills the view; there is no floor."""
    rays = pixel_rays()
    return organized_cloud(np.full(len(rays), 2000.0), rays)


def level_gravity() -> dai.IMUData:
    """Accelerometer reading of a level camera at rest: world-up is camera -y."""
    packet = dai.IMUPacket()
    packet.acceleroMeter.y = -9.81
    msg = dai.IMUData()
    msg.packets = [packet]
    return msg


def poll(predicate, *, between=None, interval=0.03, timeout=10):
    """Wait until ``predicate()`` holds, calling ``between()`` on every retry."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        if between is not None:
            between()
        time.sleep(interval)
    return predicate()


class HostSource(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()
        self.input = self.createInput()
        self.out = self.createOutput()

    def run(self):
        while self.isRunning():
            try:
                self.out.send(self.input.get())
            except dai.MessageQueue.QueueException:
                return


class ObstaclePathTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = dai.Pipeline(False)
        cloud, imu = [self.pipeline.create(HostSource) for _ in range(2)]
        self.clouds = cloud.input.createInputQueue()
        self.imus = imu.input.createInputQueue()
        node = self.pipeline.create(
            PointCloudObjectDetectionNode,
            hfov_deg=HFOV_DEG,
            danger_zone=DANGER_ZONE,
            warning_zone=WARNING_ZONE,
        ).build(
            pcl=cloud.out,
            imu=imu.out,
            pointcloud_size=POINTCLOUD_SIZE,
            intrinsics=(FX, FY, CX, CY),
            frame_size=POINTCLOUD_SIZE,
        )
        self.statuses_out = node.out_plane_valid.createOutputQueue()
        self.obstacles_out = node.out_obstacles.createOutputQueue()
        self.pipeline.start()
        self.addCleanup(self.pipeline.wait)
        self.addCleanup(self.pipeline.stop)
        self._sequence = 0
        self._statuses = {}
        self._obstacles = {}

    def send(self, points: np.ndarray) -> None:
        """Send one gravity reading and one organized RGB cloud frame, like RGBD's."""
        self._sequence += 1
        self.imus.send(level_gravity())
        cloud = dai.PointCloudData()
        cloud.setPointsRGB(points, np.full((len(points), 4), 128, dtype=np.uint8))
        cloud.setSize(*POINTCLOUD_SIZE)
        cloud.setSequenceNum(self._sequence)
        cloud.setTimestamp(timedelta(seconds=self._sequence / 30))
        self.clouds.send(cloud)

    def frames(self) -> list[tuple[bool, list]]:
        """Plane validity and obstacles of every frame both outputs reported so far."""
        for queue, by_sequence in (
            (self.statuses_out, self._statuses),
            (self.obstacles_out, self._obstacles),
        ):
            while (msg := queue.tryGet()) is not None:
                by_sequence[msg.getSequenceNum()] = msg
        return [
            (self._statuses[seq].plane_valid, self._obstacles[seq].obstacles)
            for seq in sorted(self._statuses.keys() & self._obstacles.keys())
        ]

    def stream_until(self, points: np.ndarray, predicate) -> list[tuple[bool, list]]:
        """Stream ``points`` until ``predicate(frames)`` holds and return the frames."""
        self.assertTrue(
            poll(lambda: predicate(self.frames()), between=lambda: self.send(points)),
            self.frames()[-5:],
        )
        return self.frames()

    @staticmethod
    def valid_frames(frames):
        return [obstacles for valid, obstacles in frames if valid]

    def test_flat_floor_gives_a_valid_plane_and_no_obstacles(self):
        frames = self.stream_until(
            flat_floor(), lambda frames: len(self.valid_frames(frames)) >= 10
        )
        self.assertEqual([o for o in self.valid_frames(frames) if o], [])

    def test_box_in_danger_zone_is_one_obstacle_at_its_distance(self):
        frames = self.stream_until(
            box_on_floor(front_mm=1500),
            lambda frames: any(self.valid_frames(frames)),
        )
        obstacles = next(o for o in self.valid_frames(frames) if o)
        self.assertEqual(len(obstacles), 1)
        self.assertAlmostEqual(obstacles[0].nearest_point_depth, 1500, delta=20)

    def test_without_a_floor_the_plane_stays_invalid_with_no_obstacles(self):
        frames = self.stream_until(wall_only(), lambda frames: len(frames) >= 30)
        self.assertEqual(frames, [(False, [])] * len(frames))


if __name__ == "__main__":
    unittest.main()
