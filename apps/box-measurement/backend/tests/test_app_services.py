"""The app registers a fixed, validated service set: confidence is kept in memory,
and calibration services forward to the support plane controller."""

import unittest
from unittest.mock import patch

import depthai as dai

from remote_services import RemoteServices

from app import App


class AppServicesTests(unittest.TestCase):
    def setUp(self):
        remote = patch.object(dai, "RemoteConnection", RemoteServices)
        remote.start()
        self.addCleanup(remote.stop)

    def services(self):
        return App().visualizer.services

    def test_set_threshold_is_reported_by_get(self):
        services = self.services()
        for threshold in (0, 1, 0.63):
            self.assertEqual(
                services["setDetectionConfidenceThreshold"]({"threshold": threshold}),
                {},
            )
            self.assertEqual(
                services["getDetectionConfidenceThreshold"]({}),
                {"threshold": threshold},
            )

    def test_invalid_thresholds_are_rejected(self):
        services = self.services()
        for threshold in (-0.1, 1.1, float("nan"), float("inf")):
            self.assertIn(
                "error",
                services["setDetectionConfidenceThreshold"]({"threshold": threshold}),
            )
        self.assertEqual(
            services["getDetectionConfidenceThreshold"]({}), {"threshold": 0.5}
        )

    def test_fresh_app_reports_default_threshold(self):
        self.services()["setDetectionConfidenceThreshold"]({"threshold": 0.63})
        self.assertEqual(
            self.services()["getDetectionConfidenceThreshold"]({}),
            {"threshold": 0.5},
        )

    def test_app_registers_exactly_the_supported_services(self):
        self.assertEqual(
            set(self.services()),
            {
                "getDetectionConfidenceThreshold",
                "setDetectionConfidenceThreshold",
                "getSupportPlaneCalibrationStatus",
                "confirmSupportPlane",
                "retrySupportPlaneCalibration",
                "selectSupportPlaneCandidate",
                "setSupportPlanePreviewActive",
                "setSupportPlaneDistanceOffset",
            },
        )


class StubSupportPlaneController:
    """Stands in for the calibration controller the pipeline creates."""

    STATUS = {
        "state": "AWAITING_CONFIRMATION",
        "candidate_count": 2,
        "selected_index": 1,
        "distance_offset_mm": 0.0,
        "camera_tilt_deg": 12.5,
        "camera_distance_mm": 1000.0,
        "corrected_camera_distance_mm": 1000.0,
    }

    def __init__(self, *, awaiting_confirmation=True):
        self.awaiting_confirmation = awaiting_confirmation
        self.closed = False
        self.cycled = []
        self.preview_active = False
        self.confirmed = False
        self.recalibrations = 0

    def get_status(self):
        if self.closed:
            raise RuntimeError("Support plane calibration is not available")
        return dict(self.STATUS)

    def confirm_candidate(self):
        if not self.awaiting_confirmation:
            return False
        self.confirmed = True
        return True

    def request_recalibration(self):
        self.recalibrations += 1

    def cycle_candidate(self, direction=1):
        if not self.awaiting_confirmation:
            return False
        self.cycled.append(direction)
        return True

    def set_preview_active(self, active):
        self.preview_active = active


class CalibrationServicesTests(unittest.TestCase):
    def setUp(self):
        remote = patch.object(dai, "RemoteConnection", RemoteServices)
        remote.start()
        self.addCleanup(remote.stop)
        self.controller = StubSupportPlaneController()
        app = App()
        app._support_plane = self.controller
        self.services = app.visualizer.services

    def test_select_candidate_steps_in_the_requested_direction(self):
        select = self.services["selectSupportPlaneCandidate"]
        self.assertEqual(select({"direction": -1}), {})
        self.assertEqual(select({"direction": 1}), {})
        self.assertEqual(self.controller.cycled, [-1, 1])

    def test_select_candidate_rejects_a_missing_or_invalid_direction(self):
        select = self.services["selectSupportPlaneCandidate"]
        for request in ({}, {"direction": 0}, {"direction": 2}, {"direction": "x"}):
            self.assertIn("error", select(request))
        self.assertEqual(self.controller.cycled, [])

    def test_preview_follows_the_requested_state(self):
        set_active = self.services["setSupportPlanePreviewActive"]
        self.assertEqual(set_active({"active": True}), {})
        self.assertTrue(self.controller.preview_active)
        self.assertEqual(set_active({"active": False}), {})
        self.assertFalse(self.controller.preview_active)

    def test_preview_request_without_a_state_is_rejected(self):
        set_active = self.services["setSupportPlanePreviewActive"]
        set_active({"active": True})
        for request in ({}, {"active": "maybe"}):
            self.assertIn("error", set_active(request))
        self.assertTrue(self.controller.preview_active)

    def test_status_reports_the_calibration_state(self):
        self.assertEqual(
            self.services["getSupportPlaneCalibrationStatus"]({}),
            {
                "state": "AWAITING_CONFIRMATION",
                "candidate_count": 2,
                "selected_index": 1,
                "distance_offset_mm": 0.0,
                "camera_tilt_deg": 12.5,
                "camera_distance_mm": 1000.0,
                "corrected_camera_distance_mm": 1000.0,
            },
        )

    def test_status_of_a_closed_calibration_is_an_error(self):
        self.controller.closed = True
        self.assertEqual(
            self.services["getSupportPlaneCalibrationStatus"]({}),
            {"error": "Support plane calibration is not available"},
        )

    def test_confirm_activates_the_awaiting_candidate(self):
        self.assertEqual(self.services["confirmSupportPlane"]({}), {})
        self.assertTrue(self.controller.confirmed)

    def test_candidate_actions_without_an_awaiting_candidate_are_errors(self):
        self.controller.awaiting_confirmation = False
        for name, request in (
            ("confirmSupportPlane", {}),
            ("selectSupportPlaneCandidate", {"direction": 1}),
        ):
            self.assertEqual(
                self.services[name](request),
                {"error": "No support plane candidate is awaiting confirmation"},
                name,
            )

    def test_candidate_refusal_is_not_logged_as_an_error(self):
        self.controller.awaiting_confirmation = False
        with self.assertNoLogs("api.request_handler", level="ERROR"):
            self.services["confirmSupportPlane"]({})

    def test_retry_restarts_calibration(self):
        self.assertEqual(self.services["retrySupportPlaneCalibration"]({}), {})
        self.assertEqual(self.controller.recalibrations, 1)


class CalibrationServicesBeforePipelineTests(unittest.TestCase):
    def setUp(self):
        remote = patch.object(dai, "RemoteConnection", RemoteServices)
        remote.start()
        self.addCleanup(remote.stop)
        self.services = App().visualizer.services

    def test_unavailable_calibration_is_not_logged_as_an_error(self):
        with self.assertNoLogs("api.request_handler", level="ERROR"):
            self.services["getSupportPlaneCalibrationStatus"]({})

    def test_calibration_services_are_unavailable(self):
        for name, request in (
            ("getSupportPlaneCalibrationStatus", {}),
            ("confirmSupportPlane", {}),
            ("retrySupportPlaneCalibration", {}),
            ("selectSupportPlaneCandidate", {"direction": 1}),
            ("setSupportPlanePreviewActive", {"active": True}),
            ("setSupportPlaneDistanceOffset", {"offset_mm": 10}),
        ):
            self.assertEqual(
                self.services[name](request),
                {"error": "Support plane calibration is not available"},
                name,
            )
