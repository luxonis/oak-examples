from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import depthai as dai
from depthai_nodes.message import (
    Parcel,
    ParcelCuboid,
    ParcelDetections,
    ParcelMeasurement,
    ParcelMeasurements,
    SupportPlane,
)
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
measurement_snapshot = import_module("snapshot").measurement_snapshot


class SnapshotTests(unittest.TestCase):
    def test_saved_cloud_and_cuboid_belong_to_selected_candidate(self):
        plane = SupportPlane(normal=(0, 0, -1), offset_mm=1000)
        cloud = np.array([[1, 2, 920], [20, 30, 950]], dtype=np.float32)
        selected = Parcel(candidate_id=4, xyz_mm=cloud)
        detected = ParcelDetections(
            frame="common",
            plane=plane,
            items=(
                Parcel(
                    candidate_id=0, xyz_mm=np.array([[99, 99, 99]], dtype=np.float32)
                ),
                selected,
            ),
        )
        measured = ParcelMeasurements(
            frame="common",
            plane=plane,
            items=(
                ParcelMeasurement(
                    candidate_id=4,
                    status=ParcelMeasurement.Status.MEASURED,
                    cuboid=ParcelCuboid(
                        base_center_mm=(10, 20, 1000),
                        length_axis=(1, 0, 0),
                        length_mm=200,
                        width_mm=100,
                        height_mm=80,
                    ),
                ),
            ),
        )
        color = dai.ImgFrame()
        color.setSequenceNum(92)
        frame = SimpleNamespace(
            sequence=95,
            color=color,
            generation=2,
            captured_at="2026-11-25T10:00:00Z",
            axial_correction=None,
        )
        request = measurement_snapshot(
            {"track_id": 7, "candidate_id": 4, "bbox": [20, 30, 60, 70]},
            detected,
            measured,
            frame,
            {"configured_fps": 10},
            8,
        )
        self.assertIs(request.points, selected.xyz_mm)
        self.assertIs(request.color, color)
        self.assertFalse(request.points.flags.writeable)
        details = request.metadata
        self.assertEqual(details["video_sequence"], 92)
        self.assertEqual(details["support_plane"], plane.toJson())
        corners = np.array(details["cuboid"]["corners_mm"])
        np.testing.assert_allclose(corners[:4, 2], 1000)
        np.testing.assert_allclose(corners[4:, 2], 920)
        np.testing.assert_allclose(np.linalg.norm(corners[1] - corners[0]), 200)
        np.testing.assert_allclose(np.linalg.norm(corners[2] - corners[1]), 100)
        np.testing.assert_allclose(corners[4:] - corners[:4], [[0, 0, -80]] * 4)


if __name__ == "__main__":
    unittest.main()
