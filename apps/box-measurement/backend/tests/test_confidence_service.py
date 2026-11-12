"""Confidence validation and persistence retain the frontend service contract."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import depthai as dai

from app import App
from services.application_logging import ApplicationLoggingService
from services.event_export import archive_storage
from settings import settings_store


class RemoteServices:
    def __init__(self, **kwargs):
        self.services = {}

    def registerService(self, name, handler):
        self.services[name] = handler

    def registerBinaryService(self, name, handler):
        pass


class ConfidenceServiceTests(unittest.TestCase):
    def test_threshold_service_validates_persists_and_restores_saved_setting(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(dai, "RemoteConnection", RemoteServices),
            patch.object(settings_store, "STORAGE_BASE_PATH", directory),
            patch.object(archive_storage, "STORAGE_BASE_PATH", directory),
        ):
            logging = ApplicationLoggingService(Path(directory))
            self.addCleanup(logging.handler.close)
            app = App(logging)
            services = app.visualizer.services
            for threshold in (0, 1, 0.63):
                self.assertEqual(
                    services["setDetectionConfidenceThreshold"](
                        {"threshold": threshold}
                    ),
                    {},
                )
                self.assertEqual(
                    services["getSettings"]({})["detection_confidence_threshold"],
                    threshold,
                )
            for threshold in (-0.1, 1.1, float("nan"), float("inf")):
                self.assertIn(
                    "error",
                    services["setDetectionConfidenceThreshold"](
                        {"threshold": threshold}
                    ),
                )
            restored = App(logging)
            self.assertEqual(
                restored.visualizer.services["getSettings"]({})[
                    "detection_confidence_threshold"
                ],
                0.63,
            )
