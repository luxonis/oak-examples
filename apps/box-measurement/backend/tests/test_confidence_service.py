"""The detection-confidence services validate, apply and keep the threshold in memory."""

import unittest
from unittest.mock import patch

import depthai as dai

from app import App


class RemoteServices:
    def __init__(self, **kwargs):
        self.services = {}

    def registerService(self, name, handler):
        self.services[name] = handler

    def registerBinaryService(self, name, handler):
        self.services[name] = handler


class ConfidenceServiceTests(unittest.TestCase):
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

    def test_app_registers_no_settings_or_measurement_event_services(self):
        services = self.services()
        for name in (
            "getSettings",
            "updateSettings",
            "getEvents",
            "deleteEvent",
            "getEventFile",
            "getEventExportStatus",
            "createEventExport",
            "deleteEventExport",
        ):
            self.assertNotIn(name, services)
