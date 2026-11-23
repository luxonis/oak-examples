from dataclasses import dataclass
from importlib import import_module
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
domain = import_module("domain")
CalibrationPhase = domain.CalibrationPhase
CalibrationSession = domain.CalibrationSession
ParcelTracker = domain.ParcelTracker


@dataclass
class Candidate:
    plane: str


class CalibrationTests(unittest.TestCase):
    def test_calibration_requires_selection_and_rejects_stale_candidates(self):
        session = CalibrationSession()
        session.start()
        old_generation = session.generation
        session.finish([Candidate("table"), Candidate("floor")])
        self.assertEqual(session.phase, CalibrationPhase.CHOOSING)
        self.assertIsNone(session.plane)
        session.select(old_generation, 1)
        self.assertEqual(session.plane, "floor")
        session.start()
        self.assertIsNone(session.plane)
        session.finish([Candidate("new table")])
        with self.assertRaises(ValueError):
            session.select(old_generation, 0)
        session.select(session.generation, 0)
        self.assertEqual(session.plane, "new table")

    def test_overlapping_attempt_does_not_replace_active_attempt(self):
        session = CalibrationSession()
        session.start()
        generation = session.generation
        with self.assertRaises(ValueError):
            session.start()
        self.assertEqual(session.generation, generation)
        session.finish([])
        self.assertEqual(session.phase, CalibrationPhase.FAILED)
        session.start()
        self.assertEqual(session.phase, CalibrationPhase.CALIBRATING)


def parcel(candidate, x):
    return {
        "candidate_id": candidate,
        "bbox": (x, 10, x + 50, 60),
        "center_mm": (x * 2, 0, 1000),
    }


class TrackingTests(unittest.TestCase):
    def test_ids_survive_reordered_frame_local_candidate_ids(self):
        tracker = ParcelTracker()
        first = tracker.update([parcel(0, 20), parcel(1, 200)], 0)
        second = tracker.update([parcel(0, 198), parcel(1, 22)], 0.2)
        self.assertEqual(first[0]["track_id"], second[1]["track_id"])
        self.assertEqual(first[1]["track_id"], second[0]["track_id"])

    def test_one_track_cannot_be_assigned_to_two_parcels(self):
        tracker = ParcelTracker()
        tracker.update([parcel(0, 20)], 0)
        result = tracker.update([parcel(0, 20), parcel(1, 21)], 0.2)
        self.assertNotEqual(result[0]["track_id"], result[1]["track_id"])

    def test_expired_and_recalibrated_tracks_get_new_ids(self):
        tracker = ParcelTracker(max_age_seconds=1)
        first = tracker.update([parcel(0, 20)], 0)[0]["track_id"]
        after_gap = tracker.update([parcel(0, 20)], 2)[0]["track_id"]
        self.assertNotEqual(first, after_gap)
        tracker.clear()
        after_calibration = tracker.update([parcel(0, 20)], 2.1)[0]["track_id"]
        self.assertNotEqual(after_gap, after_calibration)


if __name__ == "__main__":
    unittest.main()
