"""Box observations render themselves as standard image annotations."""

import unittest
from datetime import timedelta

import depthai as dai

from pipeline_io import frame_metadata

from solutions_sdk.box_measurement import (
    BoxDimensions,
    BoxMeasurementResult,
    BoxMeasurements,
    MeasurementStatus,
)

DIMENSIONS = BoxDimensions(length_mm=200, width_mm=100, height_mm=50)


def observation(status=MeasurementStatus.MEASURED, dimensions=DIMENSIONS, track_id=7):
    bbox = dai.RotatedRect()
    bbox.center = dai.Point2f(0.5, 0.5)
    bbox.size = dai.Size2f(0.4, 0.4)
    return BoxMeasurementResult(
        track_id=track_id,
        bounding_box=bbox,
        confidence=0.8,
        track_status=dai.Tracklet.TrackingStatus.TRACKED,
        measurement_status=status,
        dimensions=dimensions,
    )


def annotation_texts(message):
    return [text.text for ann in message.annotations for text in ann.texts]


class MeasurementAnnotationTests(unittest.TestCase):
    def test_measured_box_displays_confidence_and_aggregated_units(self):
        message = BoxMeasurements([observation()], **frame_metadata()).getVisualizationMessage()
        self.assertEqual(
            annotation_texts(message),
            ["Box 7 (80%)\nH: 5.0 cm\nL: 20.0 cm W: 10.0 cm\nV: 1000 cm³"],
        )

    def test_box_without_dimensions_displays_identity_and_confidence_only(self):
        message = BoxMeasurements(
            [observation(status=MeasurementStatus.FAILED, dimensions=None)],
            **frame_metadata(),
        ).getVisualizationMessage()
        self.assertEqual(annotation_texts(message), ["Box 7 (80%)"])

    def test_box_is_outlined_by_its_bounding_box(self):
        message = BoxMeasurements([observation()], **frame_metadata()).getVisualizationMessage()
        outlines = [
            [(point.x, point.y) for point in points.points]
            for ann in message.annotations
            for points in ann.points
        ]
        self.assertEqual(len(outlines), 1)
        for actual, expected in zip(
            outlines[0], [(0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)]
        ):
            self.assertAlmostEqual(actual[0], expected[0], places=5)
            self.assertAlmostEqual(actual[1], expected[1], places=5)

    def test_empty_observations_render_nothing(self):
        message = BoxMeasurements([], **frame_metadata()).getVisualizationMessage()
        self.assertEqual(annotation_texts(message), [])
        self.assertEqual(
            [points for ann in message.annotations for points in ann.points], []
        )

    def test_annotations_carry_source_metadata(self):
        message = BoxMeasurements(
            [observation()],
            timestamp=timedelta(seconds=2),
            timestamp_device=timedelta(seconds=12),
            sequence_num=9,
        ).getVisualizationMessage()
        self.assertEqual(message.getTimestamp(), timedelta(seconds=2))
        self.assertEqual(message.getTimestampDevice(), timedelta(seconds=12))
        self.assertEqual(message.getSequenceNum(), 9)
