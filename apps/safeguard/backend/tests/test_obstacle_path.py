"""The obstacle path turns a point cloud and gravity into obstacles and a plane status."""

import time
import unittest
from datetime import timedelta
from typing import NamedTuple

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

# The camera is this high above the floor; camera axes are x right, y down, z forward.
# Level, its lowest pixel row meets the floor about 1.3 m ahead.
CAMERA_HEIGHT_MM = 500.0
MAX_DEPTH_MM = 6000.0
CLOUD_GRAY = (128, 128, 128, 128)
ZONE_COLORS = ((230, 50, 50, 255), (250, 140, 0, 255))
SUPPORT_PLANE_GREEN = (80, 200, 80, 255)

# World-down in camera axes for a level camera.
LEVEL = np.array([0.0, 1.0, 0.0])


def pitched_down(degrees: float) -> np.ndarray:
    """World-down in the axes of a camera pitched down by ``degrees``."""
    angle = np.radians(degrees)
    return np.array([0.0, np.cos(angle), np.sin(angle)])


def pixel_rays() -> np.ndarray:
    """One camera-frame ray per pixel of the organized cloud, row by row, with z = 1."""
    u, v = np.meshgrid(
        np.arange(POINTCLOUD_SIZE[0]) + 0.5, np.arange(POINTCLOUD_SIZE[1]) + 0.5
    )
    return np.column_stack(
        [((u - CX) / FX).ravel(), ((v - CY) / FY).ravel(), np.ones(u.size)]
    )


def floor_hits(rays: np.ndarray, down: np.ndarray = LEVEL) -> np.ndarray:
    """Ray lengths to a floor perpendicular to ``down``, infinite for misses."""
    along_down = rays @ down
    with np.errstate(divide="ignore"):
        return np.where(along_down > 0, CAMERA_HEIGHT_MM / along_down, np.inf)


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


def flat_floor(down: np.ndarray = LEVEL) -> np.ndarray:
    """A floor perpendicular to ``down`` and nothing else."""
    rays = pixel_rays()
    return organized_cloud(floor_hits(rays, down), rays)


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


def gravity(down: np.ndarray) -> dai.IMUData:
    """Accelerometer reading at rest, which points world-up: opposite ``down``."""
    packet = dai.IMUPacket()
    up = -9.81 * down / np.linalg.norm(down)
    packet.acceleroMeter.x, packet.acceleroMeter.y, packet.acceleroMeter.z = map(
        float, up
    )
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


class Frame(NamedTuple):
    """What the composite node reported for one input cloud."""

    status: dai.Buffer
    obstacles: list
    overlay: dai.PointCloudData

    @property
    def valid(self) -> bool:
        return self.status.valid

    def overlay_points(self, *colors) -> np.ndarray:
        """Overlay points drawn in any of ``colors``."""
        points, rgba = self.overlay.getPointsRGB()
        drawn = np.zeros(len(points), dtype=bool)
        for color in colors:
            drawn |= np.all(rgba == np.array(color, dtype=np.uint8), axis=1)
        return points[drawn]


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
        self._outputs = {
            name: (output.createOutputQueue(), {})
            for name, output in (
                ("status", node.out_support_plane_status),
                ("obstacles", node.out_obstacles),
                ("overlay", node.out_pcl),
            )
        }
        self.pipeline.start()
        self.addCleanup(self.pipeline.wait)
        self.addCleanup(self.pipeline.stop)
        self._sequence = 0

    def send(self, points: np.ndarray, down: np.ndarray) -> None:
        """Send gravity for ``down`` and one organized RGB cloud frame, like RGBD's."""
        self._sequence += 1
        self.imus.send(gravity(down))
        cloud = dai.PointCloudData()
        cloud.setPointsRGB(points, np.tile(np.uint8(CLOUD_GRAY), (len(points), 1)))
        cloud.setSize(*POINTCLOUD_SIZE)
        cloud.setSequenceNum(self._sequence)
        cloud.setTimestamp(timedelta(seconds=self._sequence / 30))
        self.clouds.send(cloud)

    def frames(self) -> list[Frame]:
        """Every frame all outputs reported so far, in sequence order."""
        for queue, by_sequence in self._outputs.values():
            while (msg := queue.tryGet()) is not None:
                by_sequence[msg.getSequenceNum()] = msg
        status, obstacles, overlay = (by_seq for _, by_seq in self._outputs.values())
        return [
            Frame(status[seq], obstacles[seq].obstacles, overlay[seq])
            for seq in sorted(status.keys() & obstacles.keys() & overlay.keys())
        ]

    def stream_until(
        self, points: np.ndarray, predicate, down=LEVEL, timeout=10
    ) -> list[Frame]:
        """Stream ``points`` until ``predicate(frames)`` holds and return the frames."""
        self.assertTrue(
            poll(
                lambda: predicate(self.frames()),
                between=lambda: self.send(points, down),
                timeout=timeout,
            ),
            [(f.valid, f.obstacles) for f in self.frames()[-5:]],
        )
        return self.frames()

    @staticmethod
    def valid_frames(frames: list[Frame]) -> list[Frame]:
        return [frame for frame in frames if frame.valid]

    def test_flat_floor_gives_a_valid_plane_and_no_obstacles(self):
        frames = self.stream_until(
            flat_floor(), lambda frames: len(self.valid_frames(frames)) >= 10
        )
        valid = self.valid_frames(frames)
        self.assertEqual([f.obstacles for f in valid if f.obstacles], [])
        camera_height = -valid[-1].status.plane.offset_mm
        self.assertAlmostEqual(camera_height, CAMERA_HEIGHT_MM, delta=5)
        # Floor points are drawn as support plane; none keep the cloud's colour.
        self.assertGreater(len(valid[-1].overlay_points(SUPPORT_PLANE_GREEN)), 0)
        self.assertEqual(len(valid[-1].overlay_points(CLOUD_GRAY)), 0)

    def test_box_in_danger_zone_is_one_obstacle_at_its_distance(self):
        frames = self.stream_until(
            box_on_floor(front_mm=1500),
            lambda frames: any(f.obstacles for f in self.valid_frames(frames)),
        )
        obstacles = next(f.obstacles for f in self.valid_frames(frames) if f.obstacles)
        self.assertEqual(len(obstacles), 1)
        self.assertAlmostEqual(obstacles[0].nearest_point_depth, 1500, delta=20)

    def assert_stays_invalid_with_no_obstacles(self, points: np.ndarray) -> None:
        frames = self.stream_until(points, lambda frames: len(frames) >= 60)
        self.assertEqual(
            [(f.valid, f.obstacles) for f in frames], [(False, [])] * len(frames)
        )

    def test_without_a_floor_the_plane_stays_invalid_with_no_obstacles(self):
        self.assert_stays_invalid_with_no_obstacles(wall_only())

    def test_a_surface_tilted_beyond_the_gravity_tolerance_stays_invalid(self):
        # A ramp rising 20 degrees ahead of a level camera fills the view.
        self.assert_stays_invalid_with_no_obstacles(flat_floor(pitched_down(20)))

    def test_support_plane_turns_invalid_once_the_floor_is_gone(self):
        floor_frames = len(
            self.stream_until(
                flat_floor(), lambda frames: any(self.valid_frames(frames))
            )
        )
        # Continuous mode refits only after three failed plane checks 0.5 s apart.
        frames = self.stream_until(
            wall_only(),
            lambda frames: any(not f.valid for f in frames[floor_frames:]),
            timeout=15,
        )
        invalid = [f for f in frames[floor_frames:] if not f.valid]
        self.assertEqual([f.obstacles for f in invalid], [[]] * len(invalid))

    def test_zone_overlay_lies_on_the_support_plane_of_a_tilted_camera(self):
        # The camera pitches 20 degrees down; its IMU reads 4 degrees off the floor
        # normal, as a slightly sloped floor or a mounting error would make it.
        floor_down = pitched_down(20)
        frames = self.stream_until(
            flat_floor(floor_down),
            lambda frames: any(self.valid_frames(frames)),
            down=pitched_down(16),
        )
        frame = self.valid_frames(frames)[-1]
        zone = frame.overlay_points(*ZONE_COLORS)
        self.assertGreater(len(zone), 0)
        plane = frame.status.plane
        distances = np.abs(zone @ np.array(plane.normal) + plane.offset_mm)
        self.assertLess(distances.max(), 1.0)


if __name__ == "__main__":
    unittest.main()
