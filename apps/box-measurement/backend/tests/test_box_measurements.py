import unittest
from contextlib import ExitStack
from datetime import timedelta

import depthai as dai
from device_lookup import setUpModule, tearDownModule  # noqa: F401
from pipeline_io import frame_metadata
from pydantic import ValidationError

from solutions_sdk.box_measurement import (
    BoxDimensions,
    BoxMeasurementResult,
    BoxMeasurements,
    MeasurementStatus,
)


class PublicMeasurementValuesTest(unittest.TestCase):
    def test_dimensions_and_observations_have_direct_fields(self):
        dimensions = BoxDimensions(length_mm=200, width_mm=100, height_mm=50)
        self.assertEqual(dimensions.volume_mm3, 1_000_000)
        with self.assertRaises(ValidationError):
            dimensions.height_mm = 60  # type: ignore[misc]
        rect = dai.RotatedRect(dai.Point2f(0.5, 0.5), dai.Size2f(0.4, 0.3), 0)
        result = BoxMeasurementResult(
            track_id=7,
            bounding_box=rect,
            confidence=0.8,
            track_status=dai.Tracklet.TrackingStatus.TRACKED,
            measurement_status=MeasurementStatus.MEASURED,
            dimensions=dimensions,
        )
        self.assertEqual(BoxMeasurements([result], **frame_metadata()).items, [result])
        self.assertEqual(result.track_id, 7)
        self.assertEqual(result.bounding_box.angle, 0)
        with self.assertRaises(ValidationError):
            result.track_id = 8  # type: ignore[misc]
        with self.assertRaises(ValidationError):
            BoxMeasurementResult(
                track_id=7,
                bounding_box=rect,
                confidence=0.8,
                track_status=dai.Tracklet.TrackingStatus.TRACKED,
                measurement_status=MeasurementStatus.MEASURED,
                dimensions=None,
            )
        with self.assertRaises(ValidationError):
            BoxMeasurementResult(
                track_id=7,
                bounding_box=(0.5, 0.5),  # type: ignore[arg-type]
                confidence=0.8,
                track_status=dai.Tracklet.TrackingStatus.TRACKED,
                measurement_status=MeasurementStatus.FAILED,
            )


class BoxMeasurementsMetadataTest(unittest.TestCase):
    def test_timestamps_and_sequence_number_are_required(self):
        metadata = {
            "timestamp": timedelta(seconds=2),
            "timestamp_device": timedelta(seconds=12),
            "sequence_num": 9,
        }
        for missing in metadata:
            given = {k: v for k, v in metadata.items() if k != missing}
            with self.subTest(missing=missing), self.assertRaises(TypeError):
                BoxMeasurements([], **given)  # type: ignore[call-arg]


class EstablishedPlaneTest(unittest.TestCase):
    def test_plane_setters_need_no_build(self):
        from solutions_sdk.box_measurement import BoxMeasurer, SupportPlane

        pipeline = dai.Pipeline(False)
        measurer = pipeline.create(BoxMeasurer)
        plane = SupportPlane(normal=(0, 0, 1), offset_mm=-1000)
        measurer.setSupportPlane(plane)
        self.assertEqual(measurer.getSupportPlane(), plane)
        measurer.clearSupportPlane()
        self.assertIsNone(measurer.getSupportPlane())

    def test_threshold_cannot_be_set_before_build(self):
        from solutions_sdk.box_measurement import BoxMeasurer

        measurer = dai.Pipeline(False).create(BoxMeasurer)
        with self.assertRaises(RuntimeError):
            measurer.setConfidenceThreshold(0.7)

    def test_build_time_threshold_configures_the_parser(self):
        from box_measurement_harness import (
            CloudSource,
            ColorSource,
            HostInference,
            patch_detector_hardware,
        )

        from solutions_sdk.box_measurement import BoxMeasurer

        previous = HostInference.threshold
        self.addCleanup(setattr, HostInference, "threshold", previous)
        HostInference.threshold = 0.5
        with ExitStack() as stack:
            patch_detector_hardware(stack)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            clouds = pipeline.create(CloudSource)
            pipeline.create(BoxMeasurer).build(
                colors.out, clouds.out, (64, 48), confidence_threshold=0.65
            )
        self.assertAlmostEqual(HostInference.threshold, 0.65, places=5)

    def test_invalid_thresholds_are_rejected_live_and_at_build(self):
        from box_measurement_harness import (
            CloudSource,
            ColorSource,
            patch_detector_hardware,
        )

        from solutions_sdk.box_measurement import BoxMeasurer

        invalid = [float("nan"), float("inf"), -0.1, 1.1]
        with ExitStack() as stack:
            patch_detector_hardware(stack)
            pipeline = dai.Pipeline(False)
            colors = pipeline.create(ColorSource)
            clouds = pipeline.create(CloudSource)
            measurer = pipeline.create(BoxMeasurer).build(
                colors.out, clouds.out, (64, 48)
            )
            for value in invalid:
                with self.assertRaises(ValueError):
                    measurer.setConfidenceThreshold(value)
            measurer.setConfidenceThreshold(0)
            measurer.setConfidenceThreshold(1)
            for value in invalid:
                with self.assertRaises(ValueError):
                    pipeline.create(BoxMeasurer).build(
                        colors.out, clouds.out, (64, 48), confidence_threshold=value
                    )

    def test_invalid_cloud_size_is_rejected_before_the_model_is_fetched(self):
        from box_measurement_harness import CloudSource, ColorSource

        from solutions_sdk.box_measurement import BoxMeasurer

        pipeline = dai.Pipeline(False)
        colors = pipeline.create(ColorSource)
        clouds = pipeline.create(CloudSource)
        for size, error in [
            ((0, 48), ValueError),
            ((64, -1), ValueError),
            ((64,), ValueError),
            ((64.0, 48), TypeError),
        ]:
            with self.subTest(size=size), self.assertRaisesRegex(error, "Point cloud"):
                pipeline.create(BoxMeasurer).build(colors.out, clouds.out, size)

    def test_established_plane_measures_public_color_and_cloud_inputs(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            cloud = app.send()
            message = app.receive()
            self.assertEqual(message.getSequenceNum(), cloud.getSequenceNum())
            self.assertEqual(message.getTimestamp(), cloud.getTimestamp())
            self.assertEqual(message.getTimestampDevice(), cloud.getTimestampDevice())
            (item,) = message.items
            self.assertEqual(item.measurement_status, MeasurementStatus.MEASURED)
            self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)
            self.assertEqual(item.track_status, dai.Tracklet.TrackingStatus.TRACKED)
            self.assertAlmostEqual(item.bounding_box.center.x, 0.5, places=5)
            self.assertAlmostEqual(item.bounding_box.size.width, 0.6, places=5)
        finally:
            app.close()

    def test_color_at_another_resolution_with_the_same_view_is_measured(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            for color_size in [(128, 96), (32, 24)]:
                cloud = app.send(color_size=color_size)
                message = app.receive()
                self.assertEqual(message.getSequenceNum(), cloud.getSequenceNum())
                (item,) = message.items
                self.assertEqual(item.measurement_status, MeasurementStatus.MEASURED)
                self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)
        finally:
            app.close()

    def test_presence_retains_aggregate_during_depth_loss_and_border_contact(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            app.send()
            first = app.receive().items[0]
            app.send(depth=False)
            failed = app.receive().items[0]
            self.assertEqual(failed.measurement_status, MeasurementStatus.FAILED)
            self.assertEqual(failed.dimensions, first.dimensions)
            app.send(coverage=0.8)
            sparse = app.receive().items[0]
            self.assertEqual(sparse.measurement_status, MeasurementStatus.FAILED)
            self.assertEqual(sparse.dimensions, first.dimensions)
            app.send(mode=2)
            border = app.receive().items[0]
            self.assertEqual(border.measurement_status, MeasurementStatus.INELIGIBLE)
            self.assertEqual(border.dimensions, first.dimensions)
            app.measurer.clearSupportPlane()
            app.send()
            cleared = app.receive().items[0]
            self.assertEqual(cleared.measurement_status, MeasurementStatus.INELIGIBLE)
            self.assertIsNone(cleared.dimensions)
            app.send(mode=0)
            self.assertEqual(app.receive().items, [])
        finally:
            app.close()

    def test_component_medians_equivalent_signs_and_absence_retention(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, -1), offset_mm=1000))
        try:
            for height in (50, 150, 100):
                app.send(height=height)
                item = app.receive().items[0]
            self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)
            for _ in range(29):
                app.send(mode=0)
                self.assertEqual(app.receive().items, [])
            app.send(depth=False)
            self.assertAlmostEqual(
                app.receive().items[0].dimensions.height_mm, 100, places=1
            )
            for _ in range(30):
                app.send(mode=0)
                app.receive()
            app.send(depth=False)
            self.assertIsNone(app.receive().items[0].dimensions)
            app.send(height=70)
            self.assertAlmostEqual(
                app.receive().items[0].dimensions.height_mm, 70, places=1
            )
        finally:
            app.close()

    def test_nonempty_match_survives_downsampling_without_cloud_pixels(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            app.send()
            first = app.receive().items[0]
            for _ in range(31):
                app.send(mode=4)
                (item,) = app.receive().items
                self.assertEqual(item.track_id, 7)
                self.assertEqual(item.measurement_status, MeasurementStatus.FAILED)
                self.assertEqual(item.dimensions, first.dimensions)
            app.measurer.clearSupportPlane()
            app.send(mode=4)
            (item,) = app.receive().items
            self.assertEqual(item.measurement_status, MeasurementStatus.INELIGIBLE)
            self.assertIsNone(item.dimensions)
        finally:
            app.close()

    def test_only_last_600_samples_contribute(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            for height in [50] * 301 + [150] * 300:
                app.send(height=height)
                item = app.receive().items[0]
            self.assertAlmostEqual(item.dimensions.height_mm, 100, places=1)
        finally:
            app.close()

    def test_live_confidence_preserves_parser_iou(self):
        from box_measurement_harness import HostInference, MeasurementPipeline

        app = MeasurementPipeline()
        try:
            app.measurer.setConfidenceThreshold(0.7)
            app.send()
            item = app.receive().items[0]
            self.assertEqual(item.measurement_status, MeasurementStatus.INELIGIBLE)
            self.assertAlmostEqual(
                HostInference.configuration.getConfidenceThreshold(), 0.7, places=5
            )
            self.assertAlmostEqual(
                HostInference.configuration.getIouThreshold(), 0.37, places=5
            )
        finally:
            app.close()

    def test_plane_change_does_not_wait_for_in_progress_geometry_or_mix_samples(self):
        from threading import Event
        from unittest.mock import patch

        import open3d as o3d
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        entered, release = Event(), Event()
        original = o3d.geometry.PointCloud.voxel_down_sample

        def delayed(cloud, *args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test did not release geometry")
            return original(cloud, *args, **kwargs)

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            with patch.object(o3d.geometry.PointCloud, "voxel_down_sample", delayed):
                app.send()
                self.assertTrue(entered.wait(5))
                app.measurer.setSupportPlane(SupportPlane(normal=(0, 0, 1), offset_mm=-1200))
                release.set()
                old = app.receive().items[0]
                self.assertAlmostEqual(old.dimensions.height_mm, 100, places=1)
                app.send()
                new = app.receive().items[0]
                self.assertAlmostEqual(new.dimensions.height_mm, 300, places=1)
        finally:
            release.set()
            app.close()

    def test_nonblocking_output_overwrites_old_observations(self):
        from box_measurement_harness import MeasurementPipeline
        from pipeline_io import receive

        app = MeasurementPipeline(max_size=1)
        try:
            for _ in range(5):
                app.send()
                receive(app.cloud_output)
            self.assertEqual(app.receive().getSequenceNum(), 5)
        finally:
            app.close()

    def test_blocking_output_applies_backpressure_until_consumed(self):
        import time

        from box_measurement_harness import MeasurementPipeline
        from pipeline_io import receive

        app = MeasurementPipeline(max_size=1, blocking=True)
        try:
            app.send()
            receive(app.cloud_output)
            app.send()
            time.sleep(0.05)
            self.assertIsNone(app.cloud_output.tryGet())
            self.assertEqual(app.receive().getSequenceNum(), 1)
            self.assertEqual(app.receive().getSequenceNum(), 2)
        finally:
            app.close()

    def test_invalid_geometry_and_empty_matches(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        app = MeasurementPipeline(SupportPlane(normal=(0, 0, 1), offset_mm=-1000))
        try:
            app.send(height=0)
            item = app.receive().items[0]
            self.assertEqual(item.measurement_status, MeasurementStatus.FAILED)
            self.assertIsNone(item.dimensions)
            app.send(mode=3)
            self.assertEqual(app.receive().items, [])
        finally:
            app.close()


class OversizedDetectionTest(unittest.TestCase):
    def setUp(self):
        from box_measurement_harness import MeasurementPipeline

        from solutions_sdk.box_measurement import SupportPlane

        self.app = MeasurementPipeline(
            SupportPlane(normal=(0, 0, 1), offset_mm=-1000), with_emitter=True
        )
        self.addCleanup(self.app.close)

    def test_detection_just_below_half_the_frame_is_measured(self):
        self.app.send(mode=6)
        (item,) = self.app.receive().items
        self.assertEqual(item.measurement_status, MeasurementStatus.MEASURED)

    def test_detection_just_above_half_the_frame_is_omitted(self):
        self.app.send(mode=5)
        self.assertEqual(self.app.receive().items, [])

    def test_track_oversized_in_some_frames_keeps_samples_from_other_frames(self):
        self.app.send(height=100)
        first = self.app.receive().items[0]
        for _ in range(40):
            self.app.send(mode=5, height=300)
            self.assertEqual(self.app.receive().items, [])
        self.app.send(depth=False)
        (item,) = self.app.receive().items
        self.assertEqual(item.track_id, 7)
        self.assertEqual(item.dimensions, first.dimensions)

    def test_application_completes_track_after_thirty_oversized_frames(self):
        from datetime import timedelta

        from depthai_pipeline.message.measurement_event import (
            MeasurementEventTrigger,
        )

        for _ in range(30):
            self.app.send()
            self.app.receive()
        for _ in range(30):
            self.app.send(mode=5)
            self.assertEqual(self.app.receive().items, [])
        triggers = []
        while (event := self.app.events.get(timedelta(seconds=5))) is not None:
            if isinstance(event, MeasurementEventTrigger):
                triggers.append(event)
            if event.getSequenceNum() >= 60:
                break
        self.assertEqual([t.track_id for t in triggers], [7])

    def test_track_oversized_from_its_first_frame_emits_no_events(self):
        from datetime import timedelta

        for _ in range(61):
            self.app.send(mode=5)
            self.assertEqual(self.app.receive().items, [])
        self.app.send(mode=6)
        self.app.receive()
        self.assertIsNone(self.app.events.get(timedelta(milliseconds=500)))
