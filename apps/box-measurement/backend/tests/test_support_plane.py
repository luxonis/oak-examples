"""Checks at the public immutable geometry/serialization boundary."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from solutions_sdk.box_measurement import SupportPlane


class SupportPlaneTests(unittest.TestCase):
    def test_normalizes_normal_and_offset_together(self):
        plane = SupportPlane(normal=(0, 0, 2), offset_mm=-1000)
        self.assertEqual(plane.normal, (0.0, 0.0, 1.0))
        self.assertEqual(plane.offset_mm, -500.0)

    def test_geometry_is_immutable_and_accepts_opposite_sign(self):
        plane = SupportPlane(normal=[0, 0, -2], offset_mm=1000)  # type: ignore[arg-type]
        self.assertEqual(plane.normal, (0.0, 0.0, -1.0))
        self.assertEqual(plane.offset_mm, 500.0)
        with self.assertRaises(ValidationError):
            plane.offset_mm = 0  # type: ignore[misc]

    def test_rejects_invalid_geometry(self):
        for normal, offset in [
            ((0, 0, 0), 1),
            ((0, 1), 1),
            ((0, float("nan"), 1), 1),
            ((0, 0, 1), float("inf")),
        ]:
            with (
                self.subTest(normal=normal, offset=offset),
                self.assertRaises(ValidationError),
            ):
                SupportPlane(normal=normal, offset_mm=offset)  # type: ignore[arg-type]

    def test_json_and_file_round_trip_only_normalized_geometry(self):
        plane = SupportPlane(normal=(0, 0, 2), offset_mm=-1000)
        self.assertEqual(
            plane.toJson(), {"normal": [0.0, 0.0, 1.0], "offset_mm": -500.0}
        )
        self.assertEqual(SupportPlane.fromJson(plane.toJson()), plane)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plane.json"
            plane.toJsonFile(path)
            self.assertEqual(SupportPlane.fromJsonFile(path), plane)
            path.write_text("broken json")
            with self.assertRaises(json.JSONDecodeError):
                SupportPlane.fromJsonFile(path)
            with self.assertRaises(OSError):
                plane.toJsonFile(Path(directory) / "missing" / "plane.json")
            with self.assertRaises(OSError):
                SupportPlane.fromJsonFile(Path(directory) / "absent.json")

    def test_rejects_non_numeric_geometry(self):
        for normal, offset in [
            ((0, 0, "up"), 1),
            ((0, 0, 1), None),
            ("001", 1),
        ]:
            with (
                self.subTest(normal=normal, offset=offset),
                self.assertRaises(ValidationError),
            ):
                SupportPlane(normal=normal, offset_mm=offset)  # type: ignore[arg-type]

    def test_accepts_numpy_scalars(self):
        plane = SupportPlane(
            normal=(np.float32(0), np.int64(0), np.float64(2)),  # type: ignore[arg-type]
            offset_mm=np.int32(-4),  # type: ignore[arg-type]
        )
        self.assertEqual(plane.normal, (0.0, 0.0, 1.0))
        self.assertEqual(plane.offset_mm, -2.0)

    def test_rejects_incompatible_json(self):
        for data in [
            {"plane_eq": [0, 0, 1, -500]},
            {"normal": [0, 0, 1]},
            {"normal": [0, 0], "offset_mm": -500},
            {"normal": [0, 0, 1], "offset_mm": -500, "version": 1},
        ]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                SupportPlane.fromJson(data)

    def test_rejects_json_of_the_wrong_type(self):
        for data in [
            None,
            [],
            {"normal": [0, 0, "1"], "offset_mm": -500},
            {"normal": [0, 0, 1], "offset_mm": None},
            {"normal": [0, 0, 1], "offset_mm": False},
            {"normal": "001", "offset_mm": -500},
        ]:
            with self.subTest(data=data), self.assertRaises(TypeError):
                SupportPlane.fromJson(data)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
