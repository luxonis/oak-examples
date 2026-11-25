from datetime import timedelta
from importlib import import_module
from pathlib import Path
import sys
import time
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import depthai as dai
from depthai_nodes.message import (
    CalibrationOutcome,
    SupportPlane,
    SupportPlaneCalibrationResult,
    SupportPlaneCandidate,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ParcelController = import_module("nodes").ParcelController
native_annotations = import_module("rendering").native_annotations


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
                ParcelController, profile={"configured_fps": 10}
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
            controller = pipeline.create(ParcelController, profile={})
            self.assertIn("error", controller.select({"generation": True, "index": 0}))
            self.assertIn(
                "error", controller.preview({"generation": 0, "index": False})
            )
            self.assertIn("error", controller.preview({"generation": 0, "index": 0}))

    def test_expected_history_status_is_not_a_service_error(self):
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(ParcelController, profile={})
            controller.scheduler.errors[7] = "Object not in frame"
            controller._publish_state()
            history = controller.get_measurements({})
            self.assertNotIn("error", history)
            self.assertEqual(history["storage_error"], "Object not in frame")
            self.assertIn("error", controller.update_measurement({"track_id": 7}))

    def test_measurement_preview_validates_revision_and_keeps_image_out_of_state(self):
        store = Mock(next_track_id=8)
        store.list_summaries.return_value = []
        store.preview.return_value = {"jpeg": "saved-jpeg"}
        with dai.Pipeline(False) as pipeline:
            controller = pipeline.create(ParcelController, profile={}, store=store)
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
            controller = pipeline.create(ParcelController, profile={}, store=store)
            self.assertEqual(
                controller.get_measurement_preview({"track_id": 7, "revision": 1}),
                {"jpeg": "saved-jpeg"},
            )


if __name__ == "__main__":
    unittest.main()
