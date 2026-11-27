from importlib import import_module
import sys
from pathlib import Path
import unittest

import depthai as dai
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
geometry = import_module("depthai_pipeline.geometry")
CameraProjection = geometry.CameraProjection
transformed_imu = geometry.transformed_imu


class GeometryTests(unittest.TestCase):
    def test_common_reference_points_use_rgb_pose_and_delivered_distortion(self):
        extrinsics = dai.Extrinsics(
            np.eye(3).tolist(),
            dai.Point3f(100, 0, 0),
            dai.CameraBoardSocket.CAM_A,
            dai.LengthUnit.MILLIMETER,
        )
        extrinsics.toDeviceId = "test-camera"
        transformation = dai.ImgTransformation(
            2000,
            1500,
            ((1000, 0, 1000), (0, 1000, 750), (0, 0, 1)),
            dai.CameraModel.Perspective,
            [0.2, 0, 0, 0, 0],
            extrinsics,
        )
        frame = dai.ImgFrame()
        frame.setWidth(2000)
        frame.setHeight(1500)
        frame.setTransformation(transformation)
        projection = CameraProjection.from_frame(frame)
        pixels, visible = projection.project(np.array(((600, 0, 1000),)))
        np.testing.assert_allclose(pixels, ((1525, 750),), atol=1e-5)
        self.assertEqual(visible.tolist(), [True])

    def test_box_coordinates_clip_to_actual_rgb_grid(self):
        projection = CameraProjection(
            (2000, 1500),
            np.array(((1000, 0, 1000), (0, 1000, 750), (0, 0, 1))),
            np.zeros(5),
            np.eye(4),
        )
        box = projection.bounds(np.array(((-1500, -1000, 1000), (1500, 1000, 1000))))
        self.assertEqual(box, [0, 0, 1999, 1499])

    def test_points_behind_rgb_camera_do_not_create_a_box(self):
        projection = CameraProjection((2000, 1500), np.eye(3), np.zeros(5), np.eye(4))
        self.assertIsNone(projection.bounds(np.array(((0, 0, -100), (20, 20, -100)))))

    def test_imu_specific_force_rotates_into_cloud_reference_without_negation(self):
        message = dai.IMUData()
        message.setSequenceNum(7)
        packet = dai.IMUPacket()
        packet.acceleroMeter.x, packet.acceleroMeter.y, packet.acceleroMeter.z = (
            0,
            -9.8,
            0,
        )
        message.packets = [packet]
        rotation = np.array(((0, -1, 0), (1, 0, 0), (0, 0, 1)))
        converted = transformed_imu(message, rotation)
        force = converted.packets[0].acceleroMeter
        np.testing.assert_allclose((force.x, force.y, force.z), (9.8, 0, 0), atol=1e-5)
        self.assertEqual(converted.getSequenceNum(), 7)
        original = message.packets[0].acceleroMeter
        np.testing.assert_allclose(
            (original.x, original.y, original.z), (0, -9.8, 0), atol=1e-5
        )


if __name__ == "__main__":
    unittest.main()
