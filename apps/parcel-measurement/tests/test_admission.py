from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import depthai as dai
from depthai_nodes.message import ParcelDetections, ParcelMeasurements, SupportPlane
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

    def complete(self, controller, sequence):
        for cls, deliver in (
            (ParcelDetections, controller._detections),
            (ParcelMeasurements, controller._measurements),
        ):
            batch = cls(frame="common", plane=controller.session.plane)
            batch.setSequenceNum(sequence)
            deliver(batch)

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
