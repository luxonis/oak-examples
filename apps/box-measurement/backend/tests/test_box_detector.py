"""BoxDetector turns a color stream alone into tracked box detections."""

import unittest
from contextlib import ExitStack
from datetime import timedelta

import box_detector_harness as harness
import depthai as dai
import numpy as np
from box_detector_harness import DetectorPipeline, ScriptedInference
from box_measurement_harness import ColorSource
from device_lookup import setUpModule, tearDownModule  # noqa: F401

from solutions_sdk.box_measurement import BoxDetector

TRACKED = dai.Tracklet.TrackingStatus.TRACKED
REMOVED = dai.Tracklet.TrackingStatus.REMOVED
NEW = dai.Tracklet.TrackingStatus.NEW
SCENE = 20
BOX_A = (0.1, 0.1, 0.3, 0.3)
BOX_B = (0.6, 0.6, 0.9, 0.9)
BOX_EMPTY = (0.4, 0.0, 0.5, 0.1)
# Overlaps BOX_A less than an exact box does, so a removed track on BOX_A would
# win the pairing if it were not dropped first.
NEAR_A = (0.1, 0.1, 0.3, 0.32)
NOWHERE = (0.0, 0.8, 0.1, 0.9)


def scene_mask():
    mask = np.full((24, 32), 255, dtype=np.uint8)
    mask[2:7, 3:10] = 0
    mask[14:22, 19:29] = 1
    return mask


def region(rows, cols):
    expected = np.zeros((24, 32), dtype=bool)
    expected[rows, cols] = True
    return expected


class BoxDetectorTests(unittest.TestCase):
    def test_tracked_box_is_detected_from_color_alone(self):
        app = DetectorPipeline()
        self.addCleanup(app.close)
        frame = app.send(mode=1)
        message = app.receive()
        self.assertEqual(message.getSequenceNum(), frame.getSequenceNum())
        self.assertEqual(message.getTimestamp(), timedelta(seconds=1))
        self.assertEqual(message.getTimestampDevice(), timedelta(seconds=11))
        (item,) = message.items
        self.assertEqual(item.track_id, 7)
        self.assertEqual(item.track_status, dai.Tracklet.TrackingStatus.TRACKED)
        self.assertAlmostEqual(item.confidence, 0.8, places=5)
        self.assertAlmostEqual(item.bounding_box.center.x, 0.5, places=5)
        self.assertAlmostEqual(item.bounding_box.center.y, 0.5, places=5)
        self.assertAlmostEqual(item.bounding_box.size.width, 0.6, places=5)
        self.assertAlmostEqual(item.bounding_box.size.height, 0.6, places=5)
        self.assertEqual(item.bounding_box.angle, 0)
        self.assertEqual(message.segmentation_mask.shape, (24, 32))
        self.assertEqual(int(message.getMask(0).sum()), 14 * 18)

    def test_only_current_tracks_with_a_nonempty_segmentation_are_kept(self):
        harness.SCRIPTED_DETECTIONS[SCENE] = (
            [(BOX_A, 0.9), (BOX_B, 0.7), (BOX_EMPTY, 0.6)],
            scene_mask(),
        )
        harness.SCRIPTED_TRACKS[SCENE] = [
            (3, NEW, BOX_B),
            (4, REMOVED, BOX_A),
            (5, TRACKED, NEAR_A),
            (9, TRACKED, NOWHERE),
            (11, TRACKED, BOX_EMPTY),
        ]
        self.addCleanup(harness.SCRIPTED_DETECTIONS.clear)
        self.addCleanup(harness.SCRIPTED_TRACKS.clear)
        app = DetectorPipeline()
        self.addCleanup(app.close)
        app.send(mode=SCENE)
        message = app.receive()
        by_track = {item.track_id: (i, item) for i, item in enumerate(message.items)}
        self.assertEqual(sorted(by_track), [3, 5])
        index_b, item_b = by_track[3]
        index_a, item_a = by_track[5]
        self.assertEqual(item_b.track_status, NEW)
        self.assertAlmostEqual(item_b.confidence, 0.7, places=5)
        self.assertAlmostEqual(item_b.bounding_box.center.x, 0.75, places=5)
        self.assertAlmostEqual(item_a.bounding_box.size.width, 0.2, places=5)
        np.testing.assert_array_equal(
            message.getMask(index_a), region(slice(2, 7), slice(3, 10))
        )
        np.testing.assert_array_equal(
            message.getMask(index_b), region(slice(14, 22), slice(19, 29))
        )
        labels = set(np.unique(message.segmentation_mask).tolist())
        self.assertEqual(labels, {0, 1, 255})

    def test_frame_without_boxes_emits_empty_detections(self):
        app = DetectorPipeline()
        self.addCleanup(app.close)
        frame = app.send(mode=0)
        message = app.receive()
        self.assertEqual(message.items, [])
        self.assertEqual(message.getSequenceNum(), frame.getSequenceNum())
        self.assertTrue((message.segmentation_mask == 255).all())


class ConfidenceThresholdTests(unittest.TestCase):
    def setUp(self):
        ScriptedInference.threshold = 0.5
        ScriptedInference.configuration = None

    def test_build_time_threshold_configures_the_parser(self):
        app = DetectorPipeline(confidence_threshold=0.65)
        self.addCleanup(app.close)
        self.assertAlmostEqual(ScriptedInference.threshold, 0.65, places=5)

    def test_live_threshold_reaches_the_parser_and_keeps_its_iou(self):
        app = DetectorPipeline()
        self.addCleanup(app.close)
        app.detector.setConfidenceThreshold(0.7)
        app.send()
        app.receive()
        config = ScriptedInference.configuration
        assert config is not None
        self.assertAlmostEqual(config.getConfidenceThreshold(), 0.7, places=5)
        self.assertAlmostEqual(config.getIouThreshold(), 0.37, places=5)

    def test_invalid_thresholds_are_rejected_live_and_at_build(self):
        with ExitStack() as stack:
            harness.patch_detector_hardware(stack)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            detector = pipeline.create(BoxDetector).build(colors.out)
            for value in [float("nan"), float("inf"), -0.1, 1.1]:
                with self.assertRaises(ValueError):
                    detector.setConfidenceThreshold(value)
            detector.setConfidenceThreshold(0)
            detector.setConfidenceThreshold(1)
            for value in [float("nan"), float("inf"), -0.1, 1.1]:
                with self.assertRaises(ValueError):
                    pipeline.create(BoxDetector).build(colors.out, value)

    def test_non_numeric_thresholds_are_type_errors(self):
        with ExitStack() as stack:
            harness.patch_detector_hardware(stack)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            detector = pipeline.create(BoxDetector).build(colors.out)
            for value in ["0.5", None, True]:
                with self.subTest(value=value), self.assertRaises(TypeError):
                    detector.setConfidenceThreshold(value)  # type: ignore[arg-type]
                with self.subTest(value=value), self.assertRaises(TypeError):
                    pipeline.create(BoxDetector).build(colors.out, value)  # type: ignore[arg-type]

    def test_threshold_cannot_be_set_before_build(self):
        detector = dai.Pipeline(False).create(BoxDetector)
        with self.assertRaises(RuntimeError):
            detector.setConfidenceThreshold(0.7)


class BuildTests(unittest.TestCase):
    def test_a_second_build_is_rejected(self):
        with ExitStack() as stack:
            harness.patch_detector_hardware(stack)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            detector = pipeline.create(BoxDetector).build(colors.out)
            with self.assertRaises(RuntimeError):
                detector.build(colors.out)


class DeviceSupportTests(unittest.TestCase):
    def test_devices_other_than_rvc4_are_rejected(self):
        with ExitStack() as stack:
            harness.patch_detector_hardware(stack, platform=dai.Platform.RVC2)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            with self.assertRaises(ValueError):
                pipeline.create(BoxDetector).build(colors.out)


if __name__ == "__main__":
    unittest.main()
