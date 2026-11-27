from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import depthai as dai
from depthai_nodes.message import SupportPlane

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
import main
from depthai_pipeline.nodes import MeasurementController
from measurement.domain import CalibrationPhase


class StartupTests(unittest.TestCase):
    def test_missing_frontend_fails_before_opening_a_camera(self):
        error = StringIO()
        with (
            patch.object(sys, "argv", ["main.py"]),
            patch.dict(main.os.environ, {}, clear=True),
            patch.object(Path, "is_file", return_value=False),
            patch.object(main.dai, "Device") as device,
            redirect_stderr(error),
        ):
            with self.assertRaises(SystemExit) as result:
                main.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("--no-frontend", error.getvalue())
        self.assertIn("npm --prefix frontend run build", error.getvalue())
        device.assert_not_called()

    def test_default_storage_stays_at_the_example_root(self):
        with (
            patch.object(sys, "argv", ["main.py", "--no-frontend"]),
            patch.dict(main.os.environ, {}, clear=True),
            patch.object(main.signal, "signal"),
            patch.object(main.dai, "RemoteConnection"),
            patch.object(main.dai, "Device") as device,
            patch.object(main.dai, "Pipeline"),
            patch.object(main, "MeasurementStore") as store,
            patch.object(main, "init_pipeline"),
        ):
            device.return_value.getPlatform.return_value = dai.Platform.RVC4
            pipeline = main.dai.Pipeline.return_value.__enter__.return_value
            pipeline.isRunning.return_value = False
            main.init_pipeline.return_value.get_state.return_value = {"capture": {}}
            main.main()
        store.assert_called_once_with(
            main.EXAMPLE_ROOT / "data" / "measure-anything.sqlite3"
        )


class VerificationLogTests(unittest.TestCase):
    def test_success_is_debug_but_rejection_remains_a_warning(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted), dai.Pipeline(False) as pipeline:
                controller = pipeline.create(MeasurementController, profile={})
                plane = SupportPlane(normal=(0, 0, -1), offset_mm=1000)
                controller.session.phase = CalibrationPhase.READY
                controller.session.plane = plane
                controller.pending_verification = (
                    controller.session.generation,
                    plane,
                    1,
                )
                result = SimpleNamespace(
                    accepted=accepted,
                    plane=plane,
                    gravity_angle_deg=0,
                    on_plane_ratio=0.5,
                    getSequenceNum=lambda: 1,
                )
                with self.assertLogs("depthai_pipeline.nodes", level="DEBUG") as logs:
                    controller._verification(result)
                levels = [record.levelname for record in logs.records]
                self.assertEqual(
                    levels, ["DEBUG"] if accepted else ["DEBUG", "WARNING"]
                )
                self.assertEqual(
                    controller.session.phase is CalibrationPhase.READY, accepted
                )


if __name__ == "__main__":
    unittest.main()
