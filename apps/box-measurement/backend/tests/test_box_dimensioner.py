"""BoxDimensioner driven with hand-built box detections and point clouds."""

import unittest

import depthai as dai
import numpy as np
from device_lookup import setUpModule, tearDownModule  # noqa: F401
from pipeline_io import flat_top_cloud, frame_metadata, receive, stamp

from solutions_sdk.box_measurement import (
    BoxDetection,
    BoxDetections,
    BoxDimensioner,
    MeasurementStatus,
    SupportPlane,
    SupportPlaneCalibrator,
)

CLOUD_SIZE = (64, 48)
FLOOR = SupportPlane(normal=(0, 0, 1), offset_mm=-1000)


class DetectionSource(dai.node.HostNode):
    def process(self, detections):
        self.out.send(detections)


class CloudSource(dai.node.HostNode):
    def process(self, cloud):
        self.out.send(cloud)


def box(track_id=7, bounds=(0.2, 0.2, 0.8, 0.8)):
    xmin, ymin, xmax, ymax = bounds
    rect = dai.RotatedRect(
        dai.Point2f((xmin + xmax) / 2, (ymin + ymax) / 2),
        dai.Size2f(xmax - xmin, ymax - ymin),
        0,
    )
    return BoxDetection(
        track_id=track_id,
        bounding_box=rect,
        confidence=0.8,
        track_status=dai.Tracklet.TrackingStatus.TRACKED,
    )


def centered_mask(index=0):
    mask = np.full((24, 32), 255, dtype=np.uint8)
    mask[5:19, 7:25] = index
    return mask


class Dimensioning:
    """A host-only pipeline around a real BoxDimensioner."""

    def __init__(self, plane=None):
        self.pipeline = dai.Pipeline(False)
        detections = self.pipeline.create(DetectionSource)
        clouds = self.pipeline.create(CloudSource)
        self.detection_input = detections.inputs["detections"].createInputQueue()
        self.cloud_input = clouds.inputs["cloud"].createInputQueue()
        self.dimensioner = self.pipeline.create(BoxDimensioner).build(
            detections=detections.out,
            point_cloud=clouds.out,
            point_cloud_size=CLOUD_SIZE,
            support_plane=plane,
        )
        self.output = self.dimensioner.out.createOutputQueue(maxSize=8, blocking=False)
        self.cloud_output = self.dimensioner.box_cloud_out.createOutputQueue(
            maxSize=8, blocking=False
        )
        self.seq = 0
        self.pipeline.start()

    def send(self, items=None, mask=None, height=100, depth=True, coverage=1.0):
        """Send one frame; by default one centered box over a flat top."""
        self.seq += 1
        if items is None:
            items, mask = [box()], centered_mask()
        if mask is None:
            mask = np.full((24, 32), 255, dtype=np.uint8)
        detections = BoxDetections(items, mask, **frame_metadata(self.seq))
        cloud = flat_top_cloud(self.seq, CLOUD_SIZE, height, depth, coverage)
        self.detection_input.send(detections)
        self.cloud_input.send(cloud)
        return cloud

    def receive(self, queue=None):
        return receive(queue or self.output)

    def item(self, **kwargs):
        self.send(**kwargs)
        (item,) = self.receive().items
        return item

    def close(self):
        self.pipeline.stop()
        self.pipeline.wait()


class BoxDimensionerTest(unittest.TestCase):
    def start(self, plane: SupportPlane | None = FLOOR):
        app = Dimensioning(plane)
        self.addCleanup(app.close)
        return app

    def test_empty_detections_give_empty_output_with_cloud_timing(self):
        app = self.start()
        cloud = app.send(items=[])
        message = app.receive()
        self.assertEqual(message.items, [])
        self.assertEqual(message.getSequenceNum(), cloud.getSequenceNum())
        self.assertEqual(message.getTimestamp(), cloud.getTimestamp())
        self.assertEqual(message.getTimestampDevice(), cloud.getTimestampDevice())

    def test_build_rejects_invalid_cloud_size_and_a_second_build(self):
        pipeline = dai.Pipeline(False)
        source = pipeline.create(DetectionSource)
        for size in [(0, 48), (64, -1), (64,), (64, 48, 1)]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                pipeline.create(BoxDimensioner).build(source.out, source.out, size)
        for size in [(64.0, 48), (True, True), (64, True), ("64", 48), (None, 48)]:
            with (
                self.subTest(size=size),
                self.assertRaisesRegex(
                    TypeError, "^Point cloud dimensions must be integers$"
                ),
            ):
                pipeline.create(BoxDimensioner).build(source.out, source.out, size)
        dimensioner = pipeline.create(BoxDimensioner).build(
            source.out, source.out, CLOUD_SIZE
        )
        with self.assertRaises(RuntimeError):
            dimensioner.build(source.out, source.out, CLOUD_SIZE)

    def test_dimensioner_and_calibrator_accept_the_same_cloud_sizes(self):
        def outcome(build, size):
            try:
                build(size)
            except (TypeError, ValueError) as error:
                return f"{type(error).__name__}: {error}"
            return "accepted"

        pipeline = dai.Pipeline(False)
        source = pipeline.create(DetectionSource)
        for size in [
            (1, 1),
            (64, 48),
            (0, 48),
            (64, -1),
            (64,),
            (64, 48, 1),
            (64.0, 48),
            ("64", 48),
            (True, True),
            (64, False),
        ]:
            with self.subTest(size=size):
                self.assertEqual(
                    outcome(
                        lambda s: pipeline.create(BoxDimensioner).build(
                            source.out, source.out, s
                        ),
                        size,
                    ),
                    outcome(
                        lambda s: pipeline.create(SupportPlaneCalibrator).build(
                            source.out, source.out, s
                        ),
                        size,
                    ),
                )

    def test_plane_methods_work_before_build(self):
        dimensioner = dai.Pipeline(False).create(BoxDimensioner)
        self.assertIsNone(dimensioner.getSupportPlane())
        dimensioner.setSupportPlane(FLOOR)
        self.assertEqual(dimensioner.getSupportPlane(), FLOOR)
        dimensioner.clearSupportPlane()
        self.assertIsNone(dimensioner.getSupportPlane())
        with self.assertRaises(TypeError):
            dimensioner.setSupportPlane((0, 0, 1, -1000))  # type: ignore[arg-type]

    def test_measured_box_carries_detection_fields_and_a_sample(self):
        app = self.start()
        item = app.item()
        self.assertEqual(item.measurement_status, MeasurementStatus.MEASURED)
        self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)
        self.assertEqual(item.track_id, 7)
        self.assertAlmostEqual(item.confidence, 0.8, places=5)
        self.assertEqual(item.track_status, dai.Tracklet.TrackingStatus.TRACKED)
        self.assertAlmostEqual(item.bounding_box.center.x, 0.5, places=5)
        self.assertAlmostEqual(item.bounding_box.size.width, 0.6, places=5)

    def test_without_plane_boxes_are_ineligible_without_dimensions(self):
        app = self.start(plane=None)
        item = app.item()
        self.assertEqual(item.measurement_status, MeasurementStatus.INELIGIBLE)
        self.assertIsNone(item.dimensions)

    def test_border_box_is_ineligible_and_keeps_the_aggregate(self):
        app = self.start()
        first = app.item()
        for bounds in [(0.04, 0.2, 0.8, 0.8), (0.2, 0.2, 0.8, 0.96)]:
            border = app.item(items=[box(bounds=bounds)], mask=centered_mask())
            self.assertEqual(border.measurement_status, MeasurementStatus.INELIGIBLE)
            self.assertEqual(border.dimensions, first.dimensions)
        inside = app.item(
            items=[box(bounds=(0.06, 0.2, 0.8, 0.8))], mask=centered_mask()
        )
        self.assertEqual(inside.measurement_status, MeasurementStatus.MEASURED)

    def test_too_few_valid_points_under_the_mask_fail(self):
        app = self.start()
        first = app.item()
        for kwargs in [{"depth": False}, {"coverage": 0.8}]:
            failed = app.item(**kwargs)
            self.assertEqual(failed.measurement_status, MeasurementStatus.FAILED)
            self.assertEqual(failed.dimensions, first.dimensions)

    def test_failed_box_without_samples_has_no_dimensions(self):
        app = self.start()
        failed = app.item(height=0)
        self.assertEqual(failed.measurement_status, MeasurementStatus.FAILED)
        self.assertIsNone(failed.dimensions)

    def test_aggregate_is_the_median_of_samples(self):
        app = self.start()
        *_, item = [app.item(height=height) for height in (50, 150, 100)]
        self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)

    def test_only_the_last_600_samples_contribute(self):
        app = self.start()
        *_, item = [app.item(height=h) for h in [50] * 301 + [150] * 300]
        self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)

    def test_tracks_are_aggregated_independently(self):
        app = self.start()
        left = (0.1, 0.2, 0.45, 0.8)
        right = (0.55, 0.2, 0.9, 0.8)
        mask = np.full((24, 32), 255, dtype=np.uint8)
        mask[5:19, 4:14] = 0
        mask[5:19, 18:28] = 1
        app.send(items=[box(1, left), box(2, right)], mask=mask)
        first, second = app.receive().items
        self.assertEqual((first.track_id, second.track_id), (1, 2))
        self.assertEqual(first.measurement_status, MeasurementStatus.MEASURED)
        self.assertEqual(second.measurement_status, MeasurementStatus.MEASURED)

    def test_absent_track_samples_survive_29_frames_and_drop_at_30(self):
        app = self.start()
        app.item(height=100)
        for _ in range(29):
            app.send(items=[])
            self.assertEqual(app.receive().items, [])
        kept = app.item(depth=False)
        self.assertAlmostEqual(kept.dimensions.height_mm, 100, places=1)
        for _ in range(30):
            app.send(items=[])
            app.receive()
        reappeared = app.item(depth=False)
        self.assertIsNone(reappeared.dimensions)
        fresh = app.item(height=70)
        self.assertAlmostEqual(fresh.dimensions.height_mm, 70, places=1)

    def test_setting_or_clearing_the_plane_resets_samples(self):
        app = self.start()
        app.item(height=100)
        app.dimensioner.setSupportPlane(SupportPlane(normal=(0, 0, 1), offset_mm=-1200))
        moved = app.item()
        self.assertAlmostEqual(moved.dimensions.height_mm, 300, places=1)
        app.dimensioner.setSupportPlane(FLOOR)
        self.assertIsNone(app.item(depth=False).dimensions)
        app.item(height=100)
        app.dimensioner.clearSupportPlane()
        cleared = app.item()
        self.assertEqual(cleared.measurement_status, MeasurementStatus.INELIGIBLE)
        self.assertIsNone(cleared.dimensions)

    def test_sign_equivalent_planes_measure_the_same_height(self):
        app = self.start(SupportPlane(normal=(0, 0, -1), offset_mm=1000))
        item = app.item(height=100)
        self.assertEqual(item.measurement_status, MeasurementStatus.MEASURED)
        self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)

    def test_box_cloud_holds_valid_points_under_masks_with_cloud_timing(self):
        app = self.start()
        cloud = app.send()
        box_cloud = app.receive(app.cloud_output)
        points = np.asarray(box_cloud.getPoints())
        # Mask rows 5:19 of 24 and columns 7:25 of 32 cover 28 x 36 cloud cells.
        self.assertEqual(points.shape, (28 * 36, 3))
        np.testing.assert_allclose(points[:, 2], 900)
        self.assertEqual(box_cloud.getSequenceNum(), cloud.getSequenceNum())
        self.assertEqual(box_cloud.getTimestamp(), cloud.getTimestamp())
        self.assertEqual(box_cloud.getTimestampDevice(), cloud.getTimestampDevice())
        app.send(depth=False)
        self.assertEqual(np.asarray(app.receive(app.cloud_output).getPoints()).size, 0)

    def test_unorganized_cloud_yields_boxes_without_dimensions(self):
        app = self.start()
        detections = BoxDetections([box()], centered_mask(), **frame_metadata(1))
        cloud = dai.PointCloudData()
        cloud.setPoints(np.full((10, 3), 900, dtype=np.float32))
        stamp(cloud, 1)
        app.detection_input.send(detections)
        app.cloud_input.send(cloud)
        (item,) = app.receive().items
        self.assertEqual(item.measurement_status, MeasurementStatus.FAILED)
        self.assertIsNone(item.dimensions)


if __name__ == "__main__":
    unittest.main()
