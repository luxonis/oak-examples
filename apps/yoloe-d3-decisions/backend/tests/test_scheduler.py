import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scheduler import choose_track, match_observations, pixel_box, validate_refresh


class SchedulerTests(unittest.TestCase):
    def test_new_then_oldest_due_track(self):
        now = 100.0
        tracks = {
            1: {"id": 1, "seen": now, "last_started": 98.0},
            2: {"id": 2, "seen": now, "last_started": 0},
            3: {"id": 3, "seen": now, "last_started": 97.0},
        }
        self.assertEqual(choose_track(tracks, now, 1.0)["id"], 2)
        tracks[2]["last_started"] = 99.5
        self.assertEqual(choose_track(tracks, now, 1.0)["id"], 3)

    def test_stale_and_not_yet_due_are_skipped(self):
        tracks = {
            1: {"id": 1, "seen": 95.0, "last_started": 0},
            2: {"id": 2, "seen": 100.0, "last_started": 99.5},
        }
        self.assertIsNone(choose_track(tracks, 100.0, 1.0))

    def test_crop_bounds_and_refresh_validation(self):
        self.assertEqual(pixel_box((-0.1, 0.1, 0.5, 1.1), 640, 640), (0, 64, 320, 640))
        self.assertIsNone(pixel_box((0.1, 0.1, 0.11, 0.11), 640, 640))
        with self.assertRaises(ValueError):
            validate_refresh(float("nan"))

    def test_match_observations_reuses_ids_once_per_frame_and_class(self):
        tracks = {7: {"id": 7, "seen": 10.0, "label": 1, "box": [0.1, 0.1, 0.5, 0.5]}}
        observations = [
            {"label": 1, "confidence": 0.9, "box": [0.11, 0.1, 0.5, 0.5]},
            {"label": 1, "confidence": 0.8, "box": [0.12, 0.1, 0.51, 0.5]},
            {"label": 2, "confidence": 0.7, "box": [0.1, 0.1, 0.5, 0.5]},
        ]
        matched, next_id = match_observations(tracks, observations, 10.1, 8)
        self.assertEqual([item["id"] for item in matched], [7, 8, 9])
        self.assertEqual(next_id, 10)


if __name__ == "__main__":
    unittest.main()
