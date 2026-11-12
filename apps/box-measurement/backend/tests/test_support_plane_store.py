"""New calibration storage and legacy rejection through application storage API."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from solutions_sdk.box_measurement import SupportPlane
from util import support_plane_store as store


class SupportPlaneStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "support_plane.json"
        patcher = patch.object(store, "SUPPORT_PLANE_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_new_geometry_and_application_correction_survive_restart(self):
        plane = SupportPlane(normal=(0, 0, 2), offset_mm=-1000)
        store.save_plane(plane, 25)
        self.assertEqual(store.load_plane(), (plane, 25))
        self.assertEqual(
            json.loads(self.path.read_text()),
            {
                "support_plane": {"normal": [0.0, 0.0, 1.0], "offset_mm": -500.0},
                "distance_offset_mm": 25,
            },
        )

    def test_legacy_geometry_and_correction_are_rejected(self):
        self.path.write_text(
            json.dumps({"plane_eq": [0, 0, 1, -500], "distance_offset_cm": 12})
        )
        self.assertIsNone(store.load_plane())

    def test_centimeter_correction_is_rejected(self):
        self.path.write_text(
            json.dumps(
                {
                    "support_plane": {"normal": [0, 0, 1], "offset_mm": -500},
                    "distance_offset_cm": 2.5,
                }
            )
        )
        self.assertIsNone(store.load_plane())

    def test_save_errors_reach_the_service_caller(self):
        with (
            patch.object(store, "SUPPORT_PLANE_FILE", Path("/dev/null/plane.json")),
            self.assertRaises(OSError),
        ):
            store.save_plane(SupportPlane(normal=(0, 0, 1), offset_mm=-500))

    def test_missing_malformed_and_invalid_new_files_require_calibration(self):
        self.assertIsNone(store.load_plane())
        for contents in [
            "{broken",
            '{"support_plane": {"normal": [0, 0, 0], "offset_mm": -500}}',
            '{"support_plane": {"normal": [0, 0, 1], "offset_mm": -500}, "distance_offset_mm": "NaN"}',
        ]:
            with self.subTest(contents=contents):
                self.path.write_text(contents)
                self.assertIsNone(store.load_plane())
