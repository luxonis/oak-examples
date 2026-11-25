from dataclasses import replace
from datetime import timedelta
from importlib import import_module
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import depthai as dai
from depthai_nodes.message import SupportPlane
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
CameraProjection = import_module("geometry").CameraProjection
preview = import_module("preview")
PreviewRequest = preview.PreviewRequest
PreviewRenderer = preview.PreviewRenderer
PreviewRendererNode = preview.PreviewRendererNode


def transformation(size, intrinsics, pose=None, distortion=(), fisheye=False):
    extrinsics = dai.Extrinsics(
        (np.eye(4) if pose is None else pose).tolist(),
        dai.CameraBoardSocket.CAM_A,
        dai.LengthUnit.MILLIMETER,
    )
    extrinsics.toDeviceId = "preview-test"
    return dai.ImgTransformation(
        *size,
        intrinsics,
        dai.CameraModel.Fisheye if fisheye else dai.CameraModel.Perspective,
        list(distortion),
        extrinsics,
    )


def scene(sequence=1, generation=1, distortion=(), raw_pose=None, target_pose=None):
    image = np.full((48, 64, 3), 100, dtype=np.uint8)
    color = dai.ImgFrame()
    color.setCvFrame(image, dai.ImgFrame.Type.NV12)
    color.setTransformation(
        transformation(
            (64, 48), [[40, 0, 32], [0, 40, 24], [0, 0, 1]], raw_pose, distortion
        )
    )
    color.setSequenceNum(sequence)
    color.setTimestamp(timedelta(seconds=3))
    color.setTimestampDevice(timedelta(seconds=2))
    depth = dai.ImgFrame()
    values = np.full((24, 32), 1000, dtype=np.uint16)
    depth.setCvFrame(values, dai.ImgFrame.Type.RAW16)
    depth.setTransformation(
        transformation((32, 24), [[20, 0, 16], [0, 20, 12], [0, 0, 1]], target_pose)
    )
    points = np.zeros((24 * 32, 3), dtype=np.float32)
    points[:, 2] = values.reshape(-1)
    return SimpleNamespace(
        color=color,
        depth=depth,
        image=image,
        points=points,
        projection=CameraProjection.from_frame(color),
        generation=generation,
    )


def annotations(frame):
    message = dai.ImgAnnotations()
    message.setBufferMetadataFrom(frame.color)
    return message


class PreviewTests(unittest.TestCase):
    def test_python_nv12_conversion_matches_sdk_layout_and_pixels(self):
        random = np.random.default_rng(42)
        for height, width in ((12, 16), (48, 64), (14, 18)):
            with self.subTest(size=(width, height)):
                image = random.integers(0, 256, (height, width, 3), dtype=np.uint8)
                expected = dai.ImgFrame()
                expected.setCvFrame(image, dai.ImgFrame.Type.NV12)
                expected.setSequenceNum(47)
                expected.setTimestamp(timedelta(seconds=3))
                expected.setTimestampDevice(timedelta(seconds=2))
                expected.setTransformation(
                    transformation(
                        (width, height),
                        [[40, 0, width / 2], [0, 40, height / 2], [0, 0, 1]],
                    )
                )
                result = preview.nv12_frame(image, expected)
                self.assertEqual(result.getType(), dai.ImgFrame.Type.NV12)
                self.assertEqual(result.getStride(), width)
                self.assertEqual(result.fb.p2Offset, expected.fb.p2Offset)
                self.assertEqual(result.fb.p3Offset, expected.fb.p3Offset)
                self.assertEqual(result.getFrame().shape, (height * 3 // 2, width))
                np.testing.assert_array_equal(result.getFrame(), expected.getFrame())
                self.assertEqual(result.getSequenceNum(), expected.getSequenceNum())
                self.assertEqual(result.getTimestamp(), expected.getTimestamp())
                self.assertEqual(
                    result.getTimestampDevice(), expected.getTimestampDevice()
                )
                np.testing.assert_array_equal(
                    result.getTransformation().getIntrinsicMatrix(),
                    expected.getTransformation().getIntrinsicMatrix(),
                )

    def test_nv12_encoder_layout_is_compact_with_padded_camera_reference(self):
        height, width = 1500, 2000
        image = np.random.default_rng(11).integers(
            0, 256, (height, width, 3), dtype=np.uint8
        )
        expected = dai.ImgFrame()
        expected.setCvFrame(image, dai.ImgFrame.Type.NV12)
        expected.setTransformation(
            transformation(
                (width, height),
                [[1000, 0, width / 2], [0, 1000, height / 2], [0, 0, 1]],
            )
        )
        for stride in (width, 2048):
            with self.subTest(camera_stride=stride):
                reference = dai.ImgFrame()
                reference.setType(dai.ImgFrame.Type.NV12)
                reference.setSize(width, height)
                reference.setStride(stride)
                reference.fb.p2Offset = stride * 1504
                reference.fb.p3Offset = stride * 1504
                reference.setData(np.zeros(stride * 2256, dtype=np.uint8))
                reference.setTransformation(expected.getTransformation())
                result = preview.nv12_frame(image, reference)
                for field in (
                    "type",
                    "width",
                    "height",
                    "stride",
                    "bytesPP",
                    "p1Offset",
                    "p2Offset",
                    "p3Offset",
                ):
                    self.assertEqual(
                        getattr(result.fb, field), getattr(expected.fb, field), field
                    )
                np.testing.assert_array_equal(result.getData(), expected.getData())
                data = result.getData()
                luminance = np.ndarray(
                    (height, width),
                    np.uint8,
                    buffer=data,
                    offset=result.fb.p1Offset,
                    strides=(result.fb.stride, 1),
                )
                chroma = np.ndarray(
                    (height // 2, width // 2, 2),
                    np.uint8,
                    buffer=data,
                    offset=result.fb.p2Offset,
                    strides=(result.fb.stride, 2, 1),
                )
                np.testing.assert_array_equal(
                    cv2.cvtColorTwoPlane(luminance, chroma, cv2.COLOR_YUV2BGR_NV12),
                    expected.getCvFrame(),
                )

    def test_disabled_preview_returns_original_frame_without_decoding(self):
        frame = SimpleNamespace(color=object())
        self.assertIs(PreviewRenderer().render(frame), frame.color)

    def test_mapping_uses_raw_distortion_and_actual_target_rotation_and_intrinsics(
        self,
    ):
        angle = 0.1
        rotation = np.array(
            [
                [np.cos(angle), 0, np.sin(angle)],
                [0, 1, 0],
                [-np.sin(angle), 0, np.cos(angle)],
            ]
        )
        raw_pose = np.eye(4)
        raw_pose[0, 3] = 100
        target_pose = raw_pose.copy()
        target_pose[:3, :3] = rotation
        frame = scene(
            distortion=(0.2, 0, 0, 0, 0),
            raw_pose=raw_pose,
            target_pose=target_pose,
        )
        map_x, map_y = PreviewRenderer()._remap(frame)
        target_ray = rotation.T @ np.array((0.5, 0, 1))
        expected = 20 * target_ray[:2] / target_ray[2] + (16, 12)
        np.testing.assert_allclose((map_x[24, 53], map_y[24, 53]), expected, atol=1e-4)
        self.assertGreater(abs(float(map_x[24, 53]) - 53 / 2), 1)

    def test_fisheye_rgb_is_mapped_through_its_actual_lens_model(self):
        frame = scene()
        frame.color.setTransformation(
            transformation(
                (64, 48),
                [[40, 0, 32], [0, 40, 24], [0, 0, 1]],
                distortion=(0, 0, 0, 0),
                fisheye=True,
            )
        )
        frame.projection = CameraProjection.from_frame(frame.color)
        map_x, map_y = PreviewRenderer()._remap(frame)
        raw_pixel = (float(32 + 40 * np.arctan(0.5)), 24.0)
        actual = (
            cv2.getRectSubPix(map_x, (1, 1), raw_pixel)[0, 0],
            cv2.getRectSubPix(map_y, (1, 1), raw_pixel)[0, 0],
        )
        np.testing.assert_allclose(actual, (26, 12), atol=0.01)

    def test_cache_invalidates_when_geometry_changes_without_a_size_change(self):
        renderer = PreviewRenderer()
        frame = scene()
        original = renderer._remap(frame)
        self.assertIs(renderer._remap(frame), original)
        frame.projection = replace(
            frame.projection, distortion=np.array((0.2, 0, 0, 0, 0))
        )
        changed = renderer._remap(frame)
        self.assertIsNot(changed, original)
        self.assertNotEqual(original[0][24, 53], changed[0][24, 53])
        self.assertIs(renderer._remap(frame), changed)

    def test_invalid_depth_is_transparent_instead_of_becoming_a_false_near_surface(
        self,
    ):
        frame = scene()
        values = np.zeros((24, 32), dtype=np.uint16)
        values[:, 10:22] = 1500
        values[:, 22:] = 65535
        frame.depth.setCvFrame(values, dai.ImgFrame.Type.RAW16)
        colored_depth = np.full((*values.shape, 3), (10, 50, 240), dtype=np.uint8)
        result = (
            PreviewRenderer()
            .render(frame, depth=True, colored_depth=colored_depth)
            .getCvFrame()
        )
        np.testing.assert_allclose(result[24, 4], (100, 100, 100), atol=3)
        np.testing.assert_allclose(result[24, 60], (100, 100, 100), atol=3)
        np.testing.assert_allclose(result[24, 32], (55, 75, 170), atol=3)

    def test_plane_overlay_excludes_objects_background_and_invalid_depth(self):
        frame = scene()
        values = np.full((24, 32), 1000, dtype=np.uint16)
        values[:, :10] = 750
        values[:, 22:] = 1250
        values[:8, 10:22] = 0
        frame.depth.setCvFrame(values, dai.ImgFrame.Type.RAW16)
        frame.points[:, 2] = values.reshape(-1)
        plane = SupportPlane(normal=(0, 0, -1), offset_mm=1000)
        colored_depth = np.full((*values.shape, 3), (10, 50, 240), dtype=np.uint8)
        for depth in (False, True):
            with self.subTest(depth=depth):
                result = (
                    PreviewRenderer()
                    .render(
                        frame, depth=depth, plane=plane, colored_depth=colored_depth
                    )
                    .getCvFrame()
                )
                for y, x in ((24, 4), (24, 60), (8, 32)):
                    np.testing.assert_allclose(result[y, x], (100, 100, 100), atol=3)
                self.assertGreater(int(result[32, 32, 1]) - int(result[32, 32, 2]), 50)

    def test_output_preserves_source_video_identity_and_calibration(self):
        frame = scene(sequence=47)
        output = PreviewRenderer().render(
            frame,
            depth=True,
            colored_depth=np.full((24, 32, 3), (10, 50, 240), dtype=np.uint8),
        )
        self.assertEqual(output.getType(), dai.ImgFrame.Type.NV12)
        self.assertEqual(output.getSequenceNum(), frame.color.getSequenceNum())
        self.assertEqual(output.getTimestamp(), frame.color.getTimestamp())
        self.assertEqual(output.getTimestampDevice(), frame.color.getTimestampDevice())
        self.assertEqual(output.getWidth(), 64)
        self.assertEqual(output.getHeight(), 48)
        np.testing.assert_array_equal(
            output.getTransformation().getIntrinsicMatrix(),
            frame.color.getTransformation().getIntrinsicMatrix(),
        )

    def test_noncoincident_or_distorted_depth_target_is_rejected(self):
        frame = scene()
        translated = np.eye(4)
        translated[0, 3] = 10
        frame.depth.setTransformation(
            transformation((32, 24), [[20, 0, 16], [0, 20, 12], [0, 0, 1]], translated)
        )
        with self.assertRaisesRegex(ValueError, "optical center"):
            PreviewRenderer().render(frame, depth=True)
        frame.depth.setTransformation(
            transformation(
                (32, 24),
                [[20, 0, 16], [0, 20, 12], [0, 0, 1]],
                distortion=(0.1, 0, 0, 0, 0),
            )
        )
        with self.assertRaisesRegex(ValueError, "undistorted perspective"):
            PreviewRenderer().render(frame, depth=True)


class PreviewWorkerTests(unittest.TestCase):
    def test_preview_drops_old_pending_frames_and_keeps_annotations_paired(self):
        started, release = threading.Event(), threading.Event()

        def render(_renderer, frame, *_, **_kwargs):
            if frame.color.getSequenceNum() == 1:
                started.set()
                release.wait(3)
            return frame.color

        with patch.object(PreviewRenderer, "render", render):
            with dai.Pipeline(False) as pipeline:
                node = pipeline.create(PreviewRendererNode)
                inputs = node.inputFrames.createInputQueue(maxSize=1, blocking=False)
                videos = node.out.createOutputQueue()
                boxes = node.annotations.createOutputQueue()
                pipeline.start()
                try:
                    first = scene(sequence=1)
                    inputs.send(PreviewRequest(first, annotations=annotations(first)))
                    self.assertTrue(started.wait(1))
                    for sequence in (2, 3):
                        frame = scene(sequence=sequence)
                        inputs.send(
                            PreviewRequest(frame, annotations=annotations(frame))
                        )
                    release.set()
                    sequences = []
                    for _ in range(2):
                        video = videos.get(timedelta(seconds=2))
                        annotation = boxes.get(timedelta(seconds=2))
                        self.assertIsNotNone(video)
                        self.assertIsNotNone(annotation)
                        self.assertEqual(
                            video.getSequenceNum(), annotation.getSequenceNum()
                        )
                        sequences.append(video.getSequenceNum())
                    self.assertEqual(sequences, [1, 3])
                    self.assertIsNone(videos.tryGet())
                    self.assertIsNone(boxes.tryGet())
                finally:
                    release.set()
                    pipeline.stop()

    def test_generation_change_during_render_discards_both_old_video_and_annotations(
        self,
    ):
        started, release = threading.Event(), threading.Event()
        generation = [1]

        def render(_renderer, frame, *_, **_kwargs):
            if frame.generation == 1:
                started.set()
                release.wait(3)
            return frame.color

        with patch.object(PreviewRenderer, "render", render):
            with dai.Pipeline(False) as pipeline:
                node = pipeline.create(
                    PreviewRendererNode, current_generation=lambda: generation[0]
                )
                inputs = node.inputFrames.createInputQueue(maxSize=1, blocking=False)
                videos = node.out.createOutputQueue()
                boxes = node.annotations.createOutputQueue()
                pipeline.start()
                try:
                    first = scene(sequence=1, generation=1)
                    inputs.send(PreviewRequest(first, annotations=annotations(first)))
                    self.assertTrue(started.wait(1))
                    generation[0] = 2
                    release.set()
                    second = scene(sequence=2, generation=2)
                    inputs.send(PreviewRequest(second, annotations=annotations(second)))
                    self.assertEqual(
                        videos.get(timedelta(seconds=2)).getSequenceNum(), 2
                    )
                    self.assertEqual(
                        boxes.get(timedelta(seconds=2)).getSequenceNum(), 2
                    )
                    self.assertIsNone(videos.tryGet())
                    self.assertIsNone(boxes.tryGet())
                finally:
                    release.set()
                    pipeline.stop()


if __name__ == "__main__":
    unittest.main()
