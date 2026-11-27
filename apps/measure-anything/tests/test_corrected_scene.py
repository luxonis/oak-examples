from datetime import timedelta
from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import depthai as dai
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
rendering = import_module("depthai_pipeline.rendering")


class CorrectedSceneTests(unittest.TestCase):
    def scene(self):
        pose = dai.Extrinsics(
            np.eye(3).tolist(),
            dai.Point3f(0, 0, 0),
            dai.CameraBoardSocket.CAM_A,
            dai.LengthUnit.MILLIMETER,
        )
        pose.toDeviceId = "test-camera"

        def transformation(size):
            return dai.ImgTransformation(
                *size,
                [[100, 0, size[0] / 2], [0, 100, size[1] / 2], [0, 0, 1]],
                dai.CameraModel.Perspective,
                [0] * 5,
                pose,
            )

        depth = dai.ImgFrame()
        depth.setCvFrame(
            np.array([[0, 65535], [1000, 1000]], np.uint16), dai.ImgFrame.Type.RAW16
        )
        depth.setTransformation(transformation((2, 2)))
        depth.setSequenceNum(41)
        depth.setTimestamp(timedelta(seconds=3))
        depth.setTimestampDevice(timedelta(seconds=2))
        color = dai.ImgFrame()
        color.setCvFrame(np.zeros((4, 4, 3), np.uint8), dai.ImgFrame.Type.NV12)
        color.setTransformation(transformation((4, 4)))
        color.setSequenceNum(73)
        cloud = dai.PointCloudData()
        cloud.setPoints(
            np.array(
                [[1, 2, 3], [2, 3, 65535], [np.nan, 0, 0], [4, 5, 1000]], np.float32
            )
        )
        cloud.setBufferMetadataFrom(depth)
        cloud.setTransformation(depth.getTransformation())
        provenance = {
            "correction_enabled": True,
            "output_axial_convention": "target_camera_axial_z",
        }
        return {
            "color": color,
            "left": color,
            "right": color,
            "depth": depth,
            "pointCloud": cloud,
            "axialCorrection": SimpleNamespace(
                frame=depth, provenance=SimpleNamespace(to_dict=lambda: provenance)
            ),
        }

    def test_invalid_depth_rows_are_zero_for_calibration_and_detection(self):
        group = self.scene()
        original = np.array(group["pointCloud"].getPoints(), copy=True)
        with patch.object(rendering, "DEPTH_SIZE", (2, 2)):
            scene = rendering.read_scene(group, 1)
        np.testing.assert_array_equal(scene.points[:3], np.zeros((3, 3)))
        np.testing.assert_array_equal(scene.points[3], [4, 5, 1000])
        np.testing.assert_array_equal(scene.cloud.getPoints(), scene.points)
        np.testing.assert_allclose(
            group["pointCloud"].getPoints(), original, equal_nan=True
        )
        self.assertEqual(scene.cloud.getSequenceNum(), 41)
        self.assertEqual(scene.color.getSequenceNum(), 73)
        self.assertEqual(
            scene.axial_correction["output_axial_convention"], "target_camera_axial_z"
        )

    def test_replayed_nv12_stereo_uses_active_luma_and_keeps_frame_identity(self):
        group = self.scene()
        left = group["color"].clone()
        left.setStride(8)
        left.fb.p1Offset = 16
        left.fb.p2Offset = 48
        left.fb.p3Offset = 48
        data = np.full(64, 255, dtype=np.uint8)
        pixels = np.arange(16, dtype=np.uint8).reshape(4, 4)
        np.ndarray((4, 4), np.uint8, buffer=data, offset=16, strides=(8, 1))[:] = pixels
        left.setData(data)
        left.setSequenceNum(91)
        left.setTimestamp(timedelta(seconds=7))
        left.setTimestampDevice(timedelta(seconds=6))
        group["left"] = left
        group["right"] = left
        with patch.object(rendering, "DEPTH_SIZE", (2, 2)):
            scene = rendering.read_scene(group, 1)
        for delivered in (scene.left, scene.right):
            self.assertEqual(delivered.getType(), dai.ImgFrame.Type.GRAY8)
            np.testing.assert_array_equal(delivered.getCvFrame(), pixels)
            self.assertEqual(delivered.getSequenceNum(), 91)
            self.assertEqual(delivered.getTimestamp(), left.getTimestamp())
            self.assertEqual(delivered.getTimestampDevice(), left.getTimestampDevice())
            self.assertEqual(delivered.getTransformation().getSize(), (4, 4))
            np.testing.assert_array_equal(
                delivered.getTransformation().getIntrinsicMatrix(),
                left.getTransformation().getIntrinsicMatrix(),
            )
            self.assertEqual(
                rendering.reference_key(delivered), rendering.reference_key(left)
            )
        self.assertEqual(left.getType(), dai.ImgFrame.Type.NV12)
        np.testing.assert_array_equal(left.getData(), data)

    def test_native_stereo_is_retained_without_copying_or_decoding(self):
        for frame_type in (dai.ImgFrame.Type.GRAY8, dai.ImgFrame.Type.RAW8):
            with self.subTest(frame_type=frame_type):
                group = self.scene()
                left = group["color"].clone()
                left.setCvFrame(np.arange(16, dtype=np.uint8).reshape(4, 4), frame_type)
                group["left"] = left
                group["right"] = left
                with patch.object(rendering, "DEPTH_SIZE", (2, 2)):
                    scene = rendering.read_scene(group, 1)
                self.assertIs(scene.left, left)
                self.assertIs(scene.right, left)

    def test_provenance_from_a_different_depth_frame_is_rejected(self):
        group = self.scene()
        other = group["depth"].clone()
        other.setSequenceNum(42)
        group["axialCorrection"].frame = other
        with patch.object(rendering, "DEPTH_SIZE", (2, 2)):
            with self.assertRaisesRegex(RuntimeError, "must identify one frame"):
                rendering.read_scene(group, 1)

    def test_rgb_decode_is_lazy_and_matches_native_nv12_conversion(self):
        group = self.scene()
        image = np.random.default_rng(7).integers(0, 256, (4, 4, 3), dtype=np.uint8)
        group["color"].setCvFrame(image, dai.ImgFrame.Type.NV12)
        with patch.object(rendering, "DEPTH_SIZE", (2, 2)):
            scene = rendering.read_scene(group, 1)
        self.assertNotIn("image", scene.__dict__)
        np.testing.assert_array_equal(scene.image, group["color"].getCvFrame())
        self.assertIs(scene.image, scene.image)

    def test_rgb_decode_honors_active_size_row_stride_and_chroma_offset(self):
        for chroma_offset in (160, 162):
            with self.subTest(chroma_offset=chroma_offset):
                color = dai.ImgFrame()
                color.setType(dai.ImgFrame.Type.NV12)
                color.setSize(12, 8)
                color.setStride(16)
                color.fb.p2Offset = chroma_offset
                color.setData(
                    np.random.default_rng(3).integers(0, 256, 256, dtype=np.uint8)
                )
                scene = rendering.SceneFrame(
                    cloud=None,
                    color=color,
                    left=None,
                    right=None,
                    depth=None,
                    points=np.empty((0, 3)),
                    projection=None,
                    generation=0,
                )
                self.assertEqual(color.getPlaneHeight(), 10)
                self.assertEqual(scene.image.shape, (8, 12, 3))
                np.testing.assert_array_equal(scene.image, color.getCvFrame())


if __name__ == "__main__":
    unittest.main()
