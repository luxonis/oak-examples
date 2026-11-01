import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import depthai as dai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.arguments import initialize_argparser
from utils.auto_calibration import build_auto_calibration, select_stereo_resolution
from utils.dynamic_controler import DynamicCalibrationControler


class AutoCalibrationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = dai.Pipeline(False)

    def test_automatic_modes_override_sdk_flash_default(self):
        for mode, expected in (
            ("on-start", dai.AutoCalibrationConfig.ON_START),
            ("continuous", dai.AutoCalibrationConfig.CONTINUOUS),
        ):

            class Worker:
                initialConfig = dai.AutoCalibrationConfig()

                def build(self, left, right):
                    return self

            worker = Worker()
            pipeline = SimpleNamespace(create=lambda node, worker=worker: worker)
            build_auto_calibration(pipeline, None, None, mode, 15)
            self.assertFalse(worker.initialConfig.flashCalibration)
            self.assertEqual(worker.initialConfig.mode, expected)
            self.assertGreater(worker.initialConfig.validationSetSize, 0)
            self.assertEqual(worker.initialConfig.calibrationConfidenceThreshold, 0.9)

    def test_automatic_mode_ignores_manual_apply_revert_and_flash_keys(self):
        controller = self.pipeline.create(DynamicCalibrationControler)
        controller.set_automatic_mode("continuous", None)
        calls = []
        controller.set_device(
            SimpleNamespace(
                flashCalibration=lambda calibration: calls.append("flash"),
                readFactoryCalibration=lambda: calls.append("factory"),
            )
        )
        controller.set_command_input(
            SimpleNamespace(send=lambda command: calls.append("command"))
        )
        controller.new_calibration = object()
        controller.old_calibration = object()
        for key in "rRlcCnopkf":
            controller.handle_key_press(ord(key))
        self.assertEqual(calls, [])
        controller.handle_key_press(ord("q"))
        self.assertTrue(controller.wants_quit)

    def test_failed_result_does_not_replace_current_calibration(self):
        controller = self.pipeline.create(DynamicCalibrationControler)
        current = dai.CalibrationHandler()
        controller.set_current_calibration(current)
        result = dai.AutoCalibrationResult()
        result.passed = False
        controller.on_automatic_result(result)
        self.assertIs(controller.calibration, current)
        self.assertFalse(controller._automatic_result["calibrationChanged"])

    def test_validation_pass_does_not_claim_existing_calibration_changed(self):
        controller = self.pipeline.create(DynamicCalibrationControler)
        result = dai.AutoCalibrationResult()
        controller.set_current_calibration(result.calibration)
        result.passed = True
        result.dataConfidence = 0.8
        result.calibrationConfidence = 0.95
        controller.on_automatic_result(result)
        self.assertFalse(controller._automatic_result["calibrationChanged"])
        self.assertEqual(controller._automatic_result["calibrationConfidence"], 0.95)

    def test_accepted_change_is_reflected_in_hud(self):
        controller = self.pipeline.create(DynamicCalibrationControler)
        controller.set_automatic_mode("on-start", None)
        controller.set_current_calibration(dai.CalibrationHandler())
        calibration = dai.CalibrationHandler()
        calibration.setCameraIntrinsics(
            dai.CameraBoardSocket.CAM_B,
            [[500, 0, 320], [0, 500, 200], [0, 0, 1]],
            640,
            400,
        )
        result = dai.AutoCalibrationResult()
        result.passed = True
        result.calibration = calibration
        controller.on_automatic_result(result)
        self.assertEqual(
            controller.calibration.eepromToJson(), calibration.eepromToJson()
        )
        self.assertTrue(controller._automatic_result["calibrationChanged"])
        annotations = dai.ImgAnnotations()
        controller._push_help_panel(annotations, dai.ImgFrame())
        texts = [
            text.text
            for annotation in annotations.annotations
            for text in annotation.texts
        ]
        self.assertIn("Validation passed; runtime calibration active", texts)
        self.assertIn("Calibration parameters changed: True", texts)

    def test_resolution_selection_rejects_missing_or_incompatible_pair(self):
        def camera(socket, size):
            return SimpleNamespace(
                socket=socket,
                configs=[SimpleNamespace(width=size[0], height=size[1])],
            )

        left = camera(dai.CameraBoardSocket.CAM_B, (1280, 800))
        right = camera(dai.CameraBoardSocket.CAM_C, (1280, 800))
        self.assertEqual(select_stereo_resolution([left, right]), (1280, 800))
        with self.assertRaisesRegex(ValueError, "CAM_B and CAM_C"):
            select_stereo_resolution([left])
        with self.assertRaisesRegex(ValueError, "matching native"):
            select_stereo_resolution(
                [left, camera(dai.CameraBoardSocket.CAM_C, (640, 400))]
            )

    def test_manual_remains_default_and_invalid_timing_is_rejected(self):
        self.assertEqual(initialize_argparser([])[1].mode, "manual")
        for option in ("--auto-interval", "--fps_limit"):
            with self.assertRaises(SystemExit):
                initialize_argparser([option, "0"])


if __name__ == "__main__":
    unittest.main()
