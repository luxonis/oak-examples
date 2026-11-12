"""Box detections share one label mask whose values index the detection items."""

import unittest
from datetime import timedelta

import depthai as dai
import numpy as np
from pipeline_io import frame_metadata
from pydantic import ValidationError

from solutions_sdk.box_measurement import BoxDetection, BoxDetections

NEW = dai.Tracklet.TrackingStatus.NEW


def detection(track_id=7, center=(0.5, 0.5)):
    return BoxDetection(
        track_id=track_id,
        bounding_box=dai.RotatedRect(dai.Point2f(*center), dai.Size2f(0.2, 0.2), 0),
        confidence=0.8,
        track_status=dai.Tracklet.TrackingStatus.TRACKED,
    )


class BoxDetectionsMaskTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.full((4, 6), 255, dtype=np.uint8)
        self.mask[0, 0:2] = 0
        self.mask[3, 4:6] = 1
        self.detections = BoxDetections(
            [detection(7), detection(9, (0.8, 0.8))], self.mask, **frame_metadata()
        )

    def test_item_mask_selects_only_pixels_labelled_with_its_index(self):
        first = self.detections.getMask(0)
        second = self.detections.getMask(1)
        self.assertEqual(first.dtype, np.bool_)
        self.assertEqual(first.shape, (4, 6))
        self.assertEqual(list(zip(*np.nonzero(first))), [(0, 0), (0, 1)])
        self.assertEqual(list(zip(*np.nonzero(second))), [(3, 4), (3, 5)])

    def test_background_belongs_to_no_item(self):
        background = ~(self.detections.getMask(0) | self.detections.getMask(1))
        self.assertEqual(int(background.sum()), 4 * 6 - 4)

    def test_index_outside_the_items_is_rejected(self):
        for index in (-1, 2, 255):
            with self.assertRaises(IndexError):
                self.detections.getMask(index)

    def test_detection_is_immutable(self):
        with self.assertRaises(ValidationError):
            detection().track_id = 8  # type: ignore[misc]

    def test_mask_labels_must_index_items_or_be_background(self):
        mask = np.full((4, 6), 255, dtype=np.uint8)
        mask[0, 0] = 1
        with self.assertRaises(ValueError):
            BoxDetections([detection()], mask, **frame_metadata())

    def test_mask_must_be_a_two_dimensional_label_image(self):
        for mask in (
            np.full((4, 6, 1), 255, dtype=np.uint8),
            np.full((4, 6), 255, dtype=np.int32),
        ):
            with self.assertRaises(ValueError):
                BoxDetections([], mask, **frame_metadata())

    def test_mask_that_is_not_an_array_is_a_type_error(self):
        with self.assertRaises(TypeError):
            BoxDetections([], [[255]], **frame_metadata())  # type: ignore[arg-type]

    def test_timestamps_and_sequence_number_are_required(self):
        mask = np.full((4, 6), 255, dtype=np.uint8)
        metadata = {
            "timestamp": timedelta(seconds=2),
            "timestamp_device": timedelta(seconds=12),
            "sequence_num": 9,
        }
        for missing in metadata:
            given = {k: v for k, v in metadata.items() if k != missing}
            with self.subTest(missing=missing), self.assertRaises(TypeError):
                BoxDetections([], mask, **given)  # type: ignore[call-arg]

    def test_empty_detections_carry_an_all_background_mask_and_metadata(self):
        message = BoxDetections(
            [],
            np.full((4, 6), 255, dtype=np.uint8),
            timestamp=timedelta(seconds=2),
            timestamp_device=timedelta(seconds=12),
            sequence_num=9,
        )
        self.assertEqual(message.items, [])
        self.assertEqual(message.segmentation_mask.shape, (4, 6))
        self.assertEqual(message.getTimestamp(), timedelta(seconds=2))
        self.assertEqual(message.getTimestampDevice(), timedelta(seconds=12))
        self.assertEqual(message.getSequenceNum(), 9)


def annotation_texts(message):
    return [text.text for ann in message.annotations for text in ann.texts]


def outlines(message):
    return [
        [(point.x, point.y) for point in points.points]
        for ann in message.annotations
        for points in ann.points
    ]


class BoxDetectionsAnnotationTests(unittest.TestCase):
    def detections(self, **metadata):
        metadata = frame_metadata() | metadata
        mask = np.full((4, 6), 255, dtype=np.uint8)
        return BoxDetections(
            [
                detection(7),
                BoxDetection(
                    track_id=12,
                    bounding_box=detection().bounding_box,
                    confidence=0.55,
                    track_status=NEW,
                ),
            ],
            mask,
            **metadata,
        )

    def test_each_box_is_labelled_with_track_and_confidence(self):
        message = self.detections().getVisualizationMessage()
        self.assertEqual(annotation_texts(message), ["Box 7 (80%)", "Box 12 (55%)"])

    def test_each_box_is_outlined_by_its_bounding_box(self):
        message = self.detections().getVisualizationMessage()
        drawn = outlines(message)
        self.assertEqual(len(drawn), 2)
        for actual, expected in zip(
            drawn[0], [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]
        ):
            self.assertAlmostEqual(actual[0], expected[0], places=5)
            self.assertAlmostEqual(actual[1], expected[1], places=5)

    def test_empty_detections_render_nothing(self):
        message = BoxDetections(
            [], np.full((4, 6), 255, dtype=np.uint8), **frame_metadata()
        ).getVisualizationMessage()
        self.assertEqual(annotation_texts(message), [])
        self.assertEqual(outlines(message), [])

    def test_annotations_carry_source_metadata(self):
        message = self.detections(
            timestamp=timedelta(seconds=2),
            timestamp_device=timedelta(seconds=12),
            sequence_num=9,
        ).getVisualizationMessage()
        self.assertEqual(message.getTimestamp(), timedelta(seconds=2))
        self.assertEqual(message.getTimestampDevice(), timedelta(seconds=12))
        self.assertEqual(message.getSequenceNum(), 9)


if __name__ == "__main__":
    unittest.main()
