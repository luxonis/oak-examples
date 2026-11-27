from datetime import timedelta
from importlib import import_module
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import depthai as dai
from depthai_nodes.message import (
    CalibrationOutcome,
    MeasureAnythingDetections,
    MeasureAnythingMeasurements,
    SupportPlane,
    SupportPlaneCalibrationResult,
    SupportPlaneCandidate,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
MeasurementController = import_module("depthai_pipeline.nodes").MeasurementController
native_annotations = import_module("depthai_pipeline.rendering").native_annotations


class AnnotationTests(unittest.TestCase):
    def test_overlays_preserve_video_identity_and_unknown_height(self):
        frame = dai.ImgFrame()
        frame.setWidth(2000)
        frame.setHeight(1500)
        frame.setSequenceNum(103)
        frame.setTimestamp(timedelta(seconds=11))
        frame.setTimestampDevice(timedelta(seconds=8))
        message = native_annotations(
            frame,
            [
                {
                    "bbox": [200, 300, 1000, 1200],
                    "track_id": 7,
                    "dimensions_mm": [220, 160, None],
                    "status": "unknown_height",
                }
            ],
        )
        self.assertEqual(message.getSequenceNum(), 103)
        self.assertEqual(message.getTimestamp(), frame.getTimestamp())
        self.assertEqual(message.getTimestampDevice(), frame.getTimestampDevice())
        annotation = message.annotations[0]
        points = annotation.points[0].points
        self.assertAlmostEqual(points[0].x, 0.1)
        self.assertAlmostEqual(points[0].y, 0.2)
        self.assertAlmostEqual(points[2].x, 0.5)
        self.assertAlmostEqual(points[2].y, 0.8)
        self.assertEqual(annotation.texts[0].text, "ID 7 | L: 220 x W: 160 x H: ? mm")

    def test_empty_frame_clears_measurement_overlays(self):
        frame = dai.ImgFrame()
        frame.setWidth(2000)
        frame.setHeight(1500)
        message = native_annotations(frame, [])
        self.assertFalse(message.annotations[0].points)
        self.assertFalse(message.annotations[0].texts)


class ControllerServiceTests(unittest.TestCase):
    def test_failed_frame_exposes_processing_failure_and_next_frame_clears_it(self):
        from measurement.domain import CalibrationPhase

        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(MeasurementController, profile={})
            controller.session.phase = CalibrationPhase.READY
            controller.session.plane = SupportPlane(normal=(0, 0, -1), offset_mm=1000)
            controller.preview_jobs = Mock()
            for sequence, failure in ((1, "detection_failed"), (2, None)):
                color = dai.ImgFrame()
                color.setWidth(640)
                color.setHeight(480)
                color.setSequenceNum(sequence)
                frame = SimpleNamespace(
                    sequence=sequence, generation=0, color=color, projection=None
                )
                controller.inflight[sequence] = time.monotonic(), frame
                for cls, target in (
                    (MeasureAnythingDetections, controller.pending_detections),
                    (MeasureAnythingMeasurements, controller.pending_measurements),
                ):
                    target[sequence] = cls(
                        frame="CAM_A",
                        plane=None if failure else controller.session.plane,
                        outcome=cls.Outcome.FAILED if failure else cls.Outcome.SUCCESS,
                        failure_code=failure,
                    )
                controller._complete(sequence)
                controller._publish_state()
                state = controller.get_state({})
                self.assertIsNone(state["error"])
                self.assertEqual(state["frame"].get("failure_code"), failure)
                if failure:
                    self.assertIn("detection_failed", state["frame"]["message"])
                else:
                    self.assertNotIn("Frame failed", state["frame"]["message"])

    def saved_track_controller(self, pipeline):
        from measurement.domain import CalibrationPhase
        from test_domain import detected_object

        store = Mock(next_track_id=7)
        store.list_summaries.return_value = [{"track_id": 7}]
        controller = pipeline.create(MeasurementController, profile={}, store=store)
        self.assertFalse(controller.get_measurements({})["items"][0]["track_active"])
        controller.session.phase = CalibrationPhase.READY
        controller.latest_scene = SimpleNamespace(sequence=20)
        controller.next_verification_at = float("inf")
        for observation in range(10):
            controller.tracker.update(
                [detected_object(0, 20)], 100 - (9 - observation) * 0.1
            )
        controller.visible_tracks = {7}
        controller.last_measurement_at = 100
        return controller

    def test_lost_track_can_request_update_and_reappear_before_removal(self):
        from test_domain import detected_object
        from test_history import request

        with dai.Pipeline(False) as pipeline:
            controller = self.saved_track_controller(pipeline)
            controller.tracker.update([], 100.5)
            controller.visible_tracks.clear()
            controller.last_measurement_at = 100.5
            with patch("depthai_pipeline.nodes.time.monotonic", return_value=100.5):
                controller._publish_state()
                row = controller.get_measurements({})["items"][0]
                self.assertFalse(row["in_frame"])
                self.assertTrue(row["track_active"])
                with patch.object(controller, "_enqueue", return_value={"ok": True}):
                    self.assertEqual(
                        controller.update_measurement({"track_id": 7}), {"ok": True}
                    )
                controller._command(
                    SimpleNamespace(
                        action="update_measurement", payload={"track_id": 7}
                    )
                )
                controller._watchdog()
            self.assertIn(7, controller.scheduler.pending_updates)
            self.assertIsNone(controller.scheduler.error)
            self.assertIsNone(controller.scheduler.choose(21, {}))
            returned = controller.tracker.update([detected_object(1, 20)], 101)
            self.assertEqual(returned[0]["track_id"], 7)
            with patch("depthai_pipeline.nodes.time.monotonic", return_value=101):
                controller._watchdog()
            self.assertIsNone(controller.scheduler.choose(20, {7: request(7, 20)}))
            fresh = controller.scheduler.choose(21, {7: request(7, 21)})
            self.assertEqual(fresh.sequence, 21)
            self.assertIsNotNone(fresh.request_revision)
            controller.scheduler.complete(fresh)
            self.assertFalse(controller.scheduler.pending_updates)

    def test_watchdog_removes_track_and_rejects_previously_accepted_update(self):
        from test_domain import detected_object

        with dai.Pipeline(False) as pipeline:
            controller = self.saved_track_controller(pipeline)
            with patch("depthai_pipeline.nodes.time.monotonic", return_value=102):
                controller._publish_state()
                self.assertTrue(
                    controller.get_measurements({})["items"][0]["track_active"]
                )
                with patch.object(controller, "_enqueue", return_value={"ok": True}):
                    self.assertEqual(
                        controller.update_measurement({"track_id": 7}), {"ok": True}
                    )
                controller.scheduler.request_update(7, 20)
            with patch("depthai_pipeline.nodes.time.monotonic", return_value=102.001):
                controller._watchdog()
                controller._publish_state()
                row = controller.get_measurements({})["items"][0]
                self.assertFalse(row["track_active"])
                self.assertFalse(row["in_frame"])
                self.assertNotIn(7, controller.tracker.tracks)
                self.assertFalse(controller.scheduler.pending_updates)
                controller._command(
                    SimpleNamespace(
                        action="update_measurement", payload={"track_id": 7}
                    )
                )
                self.assertFalse(controller.scheduler.pending_updates)
                self.assertIn("error", controller.update_measurement({"track_id": 7}))
                self.assertIsNone(controller.get_measurements({})["storage_error"])
            returned = controller.tracker.update([detected_object(0, 20)], 102.1)
            self.assertEqual(returned[0]["track_id"], 8)
            controller.store.list_summaries.return_value.append({"track_id": 8})
            with patch("depthai_pipeline.nodes.time.monotonic", return_value=102.1):
                controller._publish_state()
            self.assertFalse(
                any(
                    row["track_active"]
                    for row in controller.get_measurements({})["items"]
                )
            )

    def wait_for(self, controller, predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            state = controller.get_state({})
            if predicate(state):
                return state
            time.sleep(0.005)
        self.fail("The pipeline node did not handle its input event.")

    def test_service_commands_drive_the_running_pipeline_node(self):
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(
                MeasurementController, profile={"configured_fps": 10}
            )
            calibration = controller.events["calibration"].createInputQueue()
            pipeline.start()
            try:
                self.assertEqual(controller.calibrate({}), {"ok": True})
                state = self.wait_for(
                    controller, lambda s: s["calibration"]["phase"] == "calibrating"
                )
                generation = state["calibration"]["generation"]
                candidate = SupportPlaneCandidate(
                    plane=SupportPlane(normal=(0, 0, -1), offset_mm=1000),
                    inlier_count=100,
                    inlier_ratio=0.8,
                )
                calibration.send(
                    SupportPlaneCalibrationResult(
                        CalibrationOutcome.SUCCEEDED, [candidate]
                    )
                )
                state = self.wait_for(
                    controller, lambda s: s["calibration"]["phase"] == "choosing"
                )
                self.assertNotIn("preview", state["calibration"]["candidates"][0])
                controller.select({"generation": generation, "index": 0})
                state = self.wait_for(
                    controller, lambda s: s["calibration"]["phase"] == "ready"
                )
                self.assertEqual(state["calibration"]["plane"]["offset_mm"], 1000)
                controller.calibrate({})
                self.wait_for(
                    controller,
                    lambda s: s["calibration"]["generation"] == generation + 1,
                )
                controller.select({"generation": generation, "index": 0})
                state = self.wait_for(controller, lambda s: s["error"] is not None)
                self.assertIn("expired", state["error"])
                self.assertEqual(state["calibration"]["phase"], "calibrating")
            finally:
                pipeline.stop()

    def test_service_rejects_boolean_candidate_identifiers(self):
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(MeasurementController, profile={})
            self.assertIn("error", controller.select({"generation": True, "index": 0}))
            self.assertIn(
                "error", controller.preview({"generation": 0, "index": False})
            )
            self.assertIn("error", controller.preview({"generation": 0, "index": 0}))

    def test_storage_failure_is_not_a_service_error(self):
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(MeasurementController, profile={})
            controller.scheduler.errors[7] = "Disk full"
            controller._publish_state()
            history = controller.get_measurements({})
            self.assertNotIn("error", history)
            self.assertEqual(history["storage_error"], "Disk full")
            self.assertIn("error", controller.update_measurement({"track_id": 7}))

    def test_measurement_preview_validates_revision_and_keeps_image_out_of_state(self):
        store = Mock(next_track_id=8)
        store.list_summaries.return_value = []
        store.preview.return_value = {"jpeg": "saved-jpeg"}
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(MeasurementController, profile={}, store=store)
            self.assertEqual(
                controller.get_measurement_preview({"track_id": 7, "revision": 2}),
                {"jpeg": "saved-jpeg"},
            )
            store.preview.assert_called_once_with(7, 2)
            for request in (
                {"track_id": True, "revision": 2},
                {"track_id": 7, "revision": False},
                {"track_id": 7, "revision": 0},
            ):
                self.assertIn("error", controller.get_measurement_preview(request))
            self.assertNotIn("saved-jpeg", str(controller.get_state({})))

    def test_persisted_preview_service_uses_flat_json_response(self):
        from test_history import MeasurementStore, request

        with TemporaryDirectory() as folder, dai.Pipeline(False) as pipeline:
            store = MeasurementStore(Path(folder) / "history.sqlite3")
            snapshot = request(7)
            snapshot.metadata["preview_jpeg"] = "saved-jpeg"
            store.save(snapshot)
            controller = pipeline.create(MeasurementController, profile={}, store=store)
            self.assertEqual(
                controller.get_measurement_preview({"track_id": 7, "revision": 1}),
                {"jpeg": "saved-jpeg"},
            )


if __name__ == "__main__":
    unittest.main()
