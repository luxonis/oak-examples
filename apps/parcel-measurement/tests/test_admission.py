from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import depthai as dai
from depthai_nodes.message import (
    ParcelDetections,
    ParcelMeasurements,
    SupportPlane,
    SupportPlaneVerificationResult,
)
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
nodes = import_module("nodes")
domain = import_module("domain")


class AdmissionTests(unittest.TestCase):
    def setup_controller(self, pipeline):
        controller = pipeline.create(nodes.ParcelController, profile={})
        controller.session.plane = SupportPlane(normal=(0, 0, -1), offset_mm=1000)
        controller.session.phase = domain.CalibrationPhase.READY
        controller.calibration_cloud = Mock()
        controller.control = Mock()
        controller.config = Mock()
        controller.detector_streams = {
            name: Mock() for name in ("cloud", "color", "left", "right")
        }
        controller._display = Mock()
        return controller

    def frame(self, sequence, generation=0):
        cloud = dai.PointCloudData()
        cloud.setSequenceNum(sequence)
        color = dai.ImgFrame()
        color.setSequenceNum(sequence)
        return SimpleNamespace(
            sequence=sequence,
            generation=generation,
            cloud=cloud,
            color=color,
            left=color,
            right=color,
            points=np.array([[1, 2, 3]], np.float32),
            axial_correction={},
            projection=None,
        )

    def complete(self, controller, sequence, plane=None):
        for cls, deliver in (
            (ParcelDetections, controller._detections),
            (ParcelMeasurements, controller._measurements),
        ):
            batch = cls(frame="common", plane=plane or controller.session.plane)
            batch.setSequenceNum(sequence)
            deliver(batch)

    def verification(self, plane, sequence, accepted=True):
        result = SupportPlaneVerificationResult(
            plane,
            gravity_angle_deg=1,
            accepted=accepted,
            on_plane_ratio=0.4 if accepted else 0.01,
        )
        result.setSequenceNum(sequence)
        return result

    def test_periodic_verification_is_single_flight_and_uses_public_control(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            controller.latest_scene = self.frame(10)
            controller.next_verification_at = 5
            controller._verify_due(4)
            controller.control.send.assert_not_called()
            controller._verify_due(5)
            controller._verify_due(20)
            self.assertEqual(controller.control.send.call_count, 1)
            control = controller.control.send.call_args.args[0]
            self.assertIsInstance(
                control.command, nodes.SupportPlaneCalibrationControl.Commands.Verify
            )
            self.assertIs(control.command.plane, controller.session.plane)
            controller._verification(self.verification(controller.session.plane, 10))
            self.assertEqual(controller.session.phase, domain.CalibrationPhase.READY)
            self.assertTrue(controller.verification["accepted"])
            controller._verify_due(20)
            self.assertEqual(controller.control.send.call_count, 2)

    def test_failed_verification_blocks_admission_and_old_result_publication(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            with patch.object(nodes, "read_scene", side_effect=lambda frame, _: frame):
                controller._scene(self.frame(1))
                controller._verify_due(5)
                controller.visible_tracks.add(11)
                controller.last_measurement_at = nodes.time.monotonic()
                controller.overlays["support_plane"] = True
                plane = controller.session.plane
                controller._verification(
                    self.verification(controller.session.plane, 1, False)
                )
                self.assertTrue(controller.session.recalibration_required)
                self.assertEqual(controller.session.generation, 1)
                self.assertFalse(controller._current_visible())
                self.assertFalse(controller.overlays["support_plane"])
                self.assertIsNone(controller.last_frame)
                self.complete(controller, 1, plane)
                controller._display.assert_not_called()
                controller._scene(self.frame(2, 1))
                self.assertEqual(
                    controller.detector_streams["cloud"].send.call_count, 1
                )
                self.assertEqual(controller._display.call_args.args[1], [])

    def test_late_verification_cannot_invalidate_a_new_calibration(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            controller.latest_scene = self.frame(10)
            controller._verify_due(5)
            old_plane = controller.session.plane
            controller._command(nodes.Command("calibrate", {}))
            controller.session.finish([SimpleNamespace(plane=old_plane)])
            controller._command(nodes.Command("select", {"generation": 1, "index": 0}))
            controller._verify_due(nodes.time.monotonic() + 10)
            self.assertEqual(controller.control.send.call_count, 3)
            controller._verification(self.verification(old_plane, 10, False))
            self.assertEqual(controller.session.phase, domain.CalibrationPhase.READY)
            self.assertFalse(controller.session.recalibration_required)
            self.assertIsNone(controller.verification)

    def test_verification_with_old_cloud_retries_without_invalidating_plane(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            controller.latest_scene = self.frame(10)
            controller._verify_due(5)
            controller._verification(
                self.verification(controller.session.plane, 9, False)
            )
            self.assertEqual(controller.session.phase, domain.CalibrationPhase.READY)
            self.assertIsNone(controller.verification)
            controller._verify_due(6)
            self.assertEqual(controller.control.send.call_count, 2)

    def test_support_plane_preview_excludes_depth(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            controller._command(
                nodes.Command("preview_options", {"depth": True, "support_plane": True})
            )
            self.assertEqual(
                controller.overlays, {"depth": False, "support_plane": True}
            )

    def test_tentative_objects_are_hidden_and_unsaved_until_tenth_observation(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            controller.store = Mock()
            controller.history_jobs = Mock()
            item = SimpleNamespace(
                candidate_id=0,
                status=SimpleNamespace(value="measured"),
                cuboid=SimpleNamespace(length_mm=100, width_mm=80, height_mm=60),
            )
            request = SimpleNamespace(track_id=1, sequence=10, request_revision=None)
            with (
                patch.object(
                    nodes, "measurement_snapshot", return_value=request
                ) as snapshot,
                patch.object(nodes, "parcel_boxes") as boxes,
            ):
                for sequence in range(1, 11):
                    boxes.return_value = [
                        {
                            "candidate_id": 0,
                            "bbox": [20, 10, 70, 60],
                            "center_mm": [40, 0, 1000],
                        }
                    ]
                    controller.inflight[sequence] = (
                        nodes.time.monotonic(),
                        self.frame(sequence),
                    )
                    controller.pending_detections[sequence] = object()
                    controller.pending_measurements[sequence] = SimpleNamespace(
                        items=[item], outcome=ParcelMeasurements.Outcome.SUCCESS
                    )
                    controller._complete(sequence)
                    if sequence < 10:
                        self.assertEqual(controller._display.call_args.args[1], [])
                        self.assertFalse(controller._current_visible())
                        snapshot.assert_not_called()
                        controller.history_jobs.send.assert_not_called()
                self.assertEqual(
                    controller._display.call_args.args[1][0]["track_id"], 1
                )
                self.assertEqual(controller._current_visible(), {1})
                snapshot.assert_called_once()
                self.assertIs(
                    controller.history_jobs.send.call_args.args[0].request, request
                )
                boxes.return_value = []
                controller.inflight[11] = nodes.time.monotonic(), self.frame(11)
                controller.pending_detections[11] = object()
                controller.pending_measurements[11] = SimpleNamespace(
                    items=[], outcome=ParcelMeasurements.Outcome.SUCCESS
                )
                controller._complete(11)
                self.assertEqual(controller._display.call_args.args[1], [])
                self.assertFalse(controller._current_visible())

    def test_two_scenes_absorb_jitter_without_unbounded_admission(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            with patch.object(nodes, "read_scene", side_effect=lambda frame, _: frame):
                for seq in (1, 2, 3):
                    controller._scene(self.frame(seq))
                self.assertEqual(
                    controller.detector_streams["cloud"].send.call_count, 2
                )
                self.complete(controller, 1)
                controller._scene(self.frame(4))
                self.assertEqual(
                    controller.detector_streams["cloud"].send.call_count, 3
                )
                self.assertEqual(list(controller.inflight), [2, 4])

    def test_recalibration_retains_outstanding_slots_and_rejects_old_results(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            plane = controller.session.plane
            with patch.object(nodes, "read_scene", side_effect=lambda frame, _: frame):
                controller._scene(self.frame(1))
                controller._scene(self.frame(2))
                controller._command(nodes.Command("calibrate", {}))
                controller.session.finish([SimpleNamespace(plane=plane)])
                controller._command(
                    nodes.Command("select", {"generation": 1, "index": 0})
                )
                controller._scene(self.frame(3, 1))
                self.assertEqual(
                    controller.detector_streams["cloud"].send.call_count, 2
                )
                self.complete(controller, 1)
                controller._display.assert_not_called()
                controller._scene(self.frame(4, 1))
                self.assertEqual(list(controller.inflight), [2, 4])

    def test_out_of_order_completion_does_not_rewind_tracking_or_video(self):
        with dai.Pipeline(False) as pipeline:
            controller = self.setup_controller(pipeline)
            with patch.object(nodes, "read_scene", side_effect=lambda frame, _: frame):
                controller._scene(self.frame(1))
                controller._scene(self.frame(2))
            self.complete(controller, 2)
            self.complete(controller, 1)
            self.assertEqual(controller._display.call_count, 1)
            self.assertEqual(controller._display.call_args.args[0].sequence, 2)
            self.assertFalse(controller.inflight)


if __name__ == "__main__":
    unittest.main()
