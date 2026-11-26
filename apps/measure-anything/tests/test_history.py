import base64
from dataclasses import replace
from datetime import timedelta
from importlib import import_module
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

import cv2
import depthai as dai
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
history = import_module("history")
MeasurementStore = history.MeasurementStore
SaveRequest = history.SaveRequest
SaveScheduler = history.SaveScheduler


def request(track_id, sequence=1, next_track_id=100):
    points = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    points.flags.writeable = False
    return SaveRequest(
        track_id=track_id,
        sequence=sequence,
        request_revision=None,
        points=points,
        metadata={
            "captured_at": "2026-11-25T12:00:00+00:00",
            "dimensions_mm": [220, 160, 110],
            "algorithm_id": "public-measure-anything-algorithm",
        },
        next_track_id=next_track_id,
    )


class MeasurementStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "history.sqlite3"
        self.store = MeasurementStore(self.path)

    def preview_request(self, track_id=7, sequence=42, right=False):
        image = np.zeros((48, 64, 3), np.uint8)
        image[:, :32] = (0, 0, 240)
        image[:, 32:] = (240, 0, 0)
        compact = dai.ImgFrame()
        compact.setCvFrame(image, dai.ImgFrame.Type.NV12)
        source = compact.getData()
        stride, offset = 80, 4002
        padded = np.full(offset + stride * 24, 80, np.uint8)
        np.ndarray((48, 64), np.uint8, padded, strides=(stride, 1))[:] = source[
            : 64 * 48
        ].reshape(48, 64)
        np.ndarray((24, 64), np.uint8, padded, offset=offset, strides=(stride, 1))[
            :
        ] = source[64 * 48 :].reshape(24, 64)
        color = dai.ImgFrame()
        color.setType(dai.ImgFrame.Type.NV12)
        color.setSize(64, 48)
        color.setStride(stride)
        color.fb.p2Offset = offset
        color.setData(padded)
        original = request(track_id, sequence)
        return replace(
            original,
            color=color,
            metadata={
                **original.metadata,
                "bbox_rgb": [36, 2, 60, 42] if right else [2, 2, 28, 42],
            },
        )

    def test_crop_uses_active_padded_rgb_region_and_survives_restart(self):
        original = self.preview_request()
        with patch.object(
            history, "object_preview", wraps=history.object_preview
        ) as crop:
            self.assertEqual(crop.call_count, 0)
            self.store.save(original)
            crop.assert_called_once_with(original.color, original.metadata["bbox_rgb"])
        reopened = MeasurementStore(self.path)
        self.assertTrue(reopened.list_summaries()[0]["has_preview"])
        self.assertNotIn("preview_jpeg", reopened.list_summaries()[0])
        encoded = reopened.preview(7, 1)["jpeg"]
        image = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), 1)
        self.assertLessEqual(image.shape[1], 160)
        self.assertLessEqual(image.shape[0], 120)
        self.assertGreater(image[:, :, 2].mean(), 200)
        self.assertLess(image[:, :, 0].mean(), 20)
        self.assertEqual(reopened.detail(7)["sequence"], 42)

    def test_update_replaces_preview_with_matching_sequence_and_revision(self):
        self.store.save(self.preview_request())
        old = self.store.preview(7, 1)["jpeg"]
        self.store.save(self.preview_request(sequence=55, right=True))
        new = self.store.preview(7, 2)["jpeg"]
        self.assertNotEqual(old, new)
        image = cv2.imdecode(np.frombuffer(base64.b64decode(new), np.uint8), 1)
        self.assertGreater(image[:, :, 0].mean(), 200)
        self.assertEqual(self.store.detail(7)["sequence"], 55)
        with self.assertRaisesRegex(KeyError, "has been updated"):
            self.store.preview(7, 1)
        self.assertEqual(len(self.store.list_summaries()), 1)

    def test_legacy_records_have_no_preview_and_failed_crop_keeps_old_record(self):
        self.store.save(request(7))
        self.assertFalse(self.store.list_summaries()[0]["has_preview"])
        self.assertIsNone(self.store.preview(7, 1)["jpeg"])
        original = self.preview_request(sequence=55)
        bad = replace(
            original, metadata={**original.metadata, "bbox_rgb": [90, 90, 95, 95]}
        )
        with self.assertRaises(ValueError):
            self.store.save(bad)
        self.assertEqual(self.store.detail(7)["revision"], 1)
        self.assertIsNone(self.store.preview(7, 1)["jpeg"])
        with self.assertRaises(KeyError):
            self.store.preview(999, 1)

    def test_restart_retains_full_cloud_metadata_and_tracking_highwater(self):
        original = request(7, sequence=42)
        self.store.save(original)
        reopened = MeasurementStore(self.path)
        summary = reopened.list_summaries()[0]
        self.assertEqual(summary["track_id"], 7)
        self.assertEqual(summary["sequence"], 42)
        self.assertEqual(summary["dimensions_mm"], [220, 160, 110])
        self.assertEqual(reopened.next_track_id, 100)
        detail = reopened.detail(7)
        self.assertEqual(detail["algorithm_id"], "public-measure-anything-algorithm")
        self.assertEqual(detail["point_cloud"]["encoding"], "float32-le-base64")
        points = np.frombuffer(
            base64.b64decode(detail["point_cloud"]["xyz"]), dtype="<f4"
        ).reshape(-1, 3)
        np.testing.assert_array_equal(points, original.points)
        summary["dimensions_mm"][0] = 999
        self.assertEqual(reopened.list_summaries()[0]["dimensions_mm"][0], 220)

    def test_update_replaces_one_batch_and_advances_revision(self):
        self.store.save(request(7, sequence=42))
        newer = replace(
            request(7, sequence=55), points=np.zeros((3, 3), dtype=np.float32)
        )
        self.store.save(newer)
        self.assertEqual(len(self.store.list_summaries()), 1)
        detail = self.store.detail(7)
        self.assertEqual(detail["revision"], 2)
        self.assertEqual(detail["sequence"], 55)
        self.assertEqual(detail["point_cloud"]["count"], 3)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM measurements").fetchone()[0], 1
            )

    def test_retention_is_twenty_latest_saves_and_highwater_survives_eviction(self):
        for track_id in range(1, 24):
            self.store.save(
                request(track_id, next_track_id=1000 if track_id == 1 else 24)
            )
        ids = [item["track_id"] for item in self.store.list_summaries()]
        self.assertEqual(ids, list(range(23, 3, -1)))
        with self.assertRaises(KeyError):
            self.store.detail(1)
        self.assertEqual(MeasurementStore(self.path).next_track_id, 1000)
        self.store.save(request(4, sequence=999, next_track_id=24))
        self.assertEqual(self.store.list_summaries()[0]["track_id"], 4)
        self.assertEqual(self.store.detail(4)["revision"], 2)

    def test_invalid_new_data_preserves_previous_committed_measurement(self):
        self.store.save(request(7, sequence=42))
        bad = replace(
            request(7, sequence=55),
            metadata={"captured_at": "now", "dimensions_mm": [float("nan"), 1, 2]},
        )
        with self.assertRaises(ValueError):
            self.store.save(bad)
        self.assertEqual(self.store.detail(7)["sequence"], 42)
        self.assertEqual(MeasurementStore(self.path).detail(7)["revision"], 1)

    def test_unknown_schema_is_reported_without_overwriting_history(self):
        self.store.save(request(7))
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(
            RuntimeError, "Unsupported measurement history schema"
        ):
            MeasurementStore(self.path)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0], 999
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM measurements").fetchone()[0], 1
            )

    def test_failed_transaction_preserves_old_batch_cache_and_highwater(self):
        self.store.save(request(7, sequence=42))
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """CREATE TRIGGER reject_write BEFORE INSERT ON measurements
                   BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END"""
            )
        with self.assertRaisesRegex(sqlite3.DatabaseError, "simulated disk failure"):
            self.store.save(request(7, sequence=55, next_track_id=1000))
        self.assertEqual(self.store.list_summaries()[0]["sequence"], 42)
        self.assertEqual(self.store.detail(7)["sequence"], 42)
        self.assertEqual(self.store.next_track_id, 100)
        self.assertEqual(MeasurementStore(self.path).next_track_id, 100)

    def test_blocked_worker_leaves_history_cache_and_admission_gate_nonblocking(self):
        import depthai as dai

        from storage_node import SaveMessage, StorageHostNode

        started, release = threading.Event(), threading.Event()
        original = self.store._read_summaries

        def blocked_read(connection):
            started.set()
            release.wait(3)
            return original(connection)

        self.store._read_summaries = blocked_read
        with dai.Pipeline(False) as pipeline:
            node = pipeline.create(StorageHostNode, store=self.store)
            jobs = node.inputJobs.createInputQueue()
            results = node.outSaved.createOutputQueue()
            scheduler = SaveScheduler()
            first = scheduler.choose(10, {1: request(1, 10)})
            pipeline.start()
            try:
                jobs.send(SaveMessage(first))
                self.assertTrue(started.wait(1))
                self.assertEqual(self.store.list_summaries(), [])
                self.assertIsNone(scheduler.choose(11, {2: request(2, 11)}))
                self.assertIsNone(results.tryGet())
                release.set()
                ack = results.get(timedelta(seconds=2))
                self.assertIsNotNone(ack)
                self.assertIsNone(ack.error)
                scheduler.complete(ack.request, ack.error)
                self.assertEqual(self.store.list_summaries()[0]["track_id"], 1)
                self.assertEqual(scheduler.choose(12, {2: request(2, 12)}).track_id, 2)
            finally:
                release.set()
                pipeline.stop()


class SaveSchedulerTests(unittest.TestCase):
    def test_busy_writer_does_not_accept_another_object_or_reuse_sequence(self):
        scheduler = SaveScheduler()
        eligible = {1: request(1, 10), 2: request(2, 10)}
        first = scheduler.choose(10, eligible)
        self.assertEqual(first.track_id, 1)
        self.assertIs(first.points, eligible[1].points)
        self.assertIsNone(scheduler.choose(11, {2: request(2, 11)}))
        scheduler.complete(first)
        self.assertIsNone(scheduler.choose(10, eligible))
        second = scheduler.choose(12, {1: request(1, 12), 2: request(2, 12)})
        self.assertEqual(second.track_id, 2)
        scheduler.complete(second)
        self.assertIsNone(scheduler.choose(13, {1: request(1, 13), 2: request(2, 13)}))

    def test_multiple_visible_objects_are_saved_once_on_successive_frames(self):
        scheduler = SaveScheduler()
        chosen = []
        for sequence in range(1, 5):
            item = scheduler.choose(
                sequence, {key: request(key, sequence) for key in (1, 2, 3)}
            )
            if item:
                chosen.append((item.track_id, item.sequence))
                scheduler.complete(item)
        self.assertEqual(chosen, [(1, 1), (2, 2), (3, 3)])
        self.assertEqual(scheduler.known_saved, {1, 2, 3})

    def test_new_arrivals_and_candidate_reordering_cannot_starve_waiting_objects(self):
        scheduler = SaveScheduler()
        first = scheduler.choose(1, {1: request(1, 1), 99: request(99, 1)})
        scheduler.complete(first)
        second = scheduler.choose(2, {2: request(2, 2), 99: request(99, 2)})
        self.assertEqual(second.track_id, 99)
        scheduler.complete(second)
        third = scheduler.choose(3, {3: request(3, 3), 2: request(2, 3)})
        self.assertEqual(third.track_id, 2)

    def test_waiting_objects_are_remembered_during_writes_and_gone_ones_are_pruned(
        self,
    ):
        scheduler = SaveScheduler()
        first = scheduler.choose(1, {1: request(1, 1)})
        self.assertIsNone(scheduler.choose(2, {2: request(2, 2), 3: request(3, 2)}))
        scheduler.retain_tracks({1, 3})
        scheduler.complete(first)
        next_item = scheduler.choose(3, {4: request(4, 3), 3: request(3, 3)})
        self.assertEqual(next_item.track_id, 3)
        self.assertNotIn(2, scheduler.waiting)

    def test_update_waits_for_new_capture_and_new_request_is_not_cleared_by_old_ack(
        self,
    ):
        scheduler = SaveScheduler()
        first = scheduler.choose(10, {1: request(1, 10)})
        scheduler.request_update(1, min_sequence=12)
        scheduler.complete(first)
        self.assertIn(1, scheduler.pending_updates)
        self.assertIsNone(scheduler.choose(12, {1: request(1, 12)}))
        newer = scheduler.choose(13, {1: request(1, 13)})
        self.assertIsNotNone(newer.request_revision)
        scheduler.complete(newer)
        self.assertFalse(scheduler.pending_updates)
        self.assertIsNone(scheduler.choose(14, {1: request(1, 14)}))

    def test_duplicate_update_requests_coalesce(self):
        scheduler = SaveScheduler(known_saved=[7])
        scheduler.request_update(7, 10)
        revision = scheduler.pending_updates[7].revision
        scheduler.request_update(7, 11)
        self.assertEqual(scheduler.pending_updates[7].revision, revision)
        self.assertEqual(scheduler.pending_updates[7].min_sequence, 10)

    def test_track_removal_cancels_update_without_losing_existing_history(self):
        scheduler = SaveScheduler(known_saved=[7])
        scheduler.request_update(7, 10)
        scheduler.retain_tracks(set())
        self.assertFalse(scheduler.pending_updates)
        self.assertIn(7, scheduler.known_saved)
        self.assertIsNone(scheduler.error)
        self.assertIsNone(scheduler.choose(11, {}))

    def test_track_removal_keeps_inflight_save_until_acknowledged(self):
        scheduler = SaveScheduler()
        first = scheduler.choose(10, {7: request(7, 10)})
        scheduler.request_update(7, 10)
        scheduler.retain_tracks(set())
        self.assertFalse(scheduler.pending_updates)
        self.assertIs(scheduler.busy, first)
        self.assertIsNone(scheduler.choose(11, {8: request(8, 11)}))
        scheduler.complete(first)
        self.assertIn(7, scheduler.known_saved)
        self.assertEqual(scheduler.choose(12, {8: request(8, 12)}).track_id, 8)

    def test_failed_save_releases_gate_but_requires_explicit_retry_for_that_track(self):
        scheduler = SaveScheduler()
        first = scheduler.choose(1, {1: request(1, 1)})
        scheduler.complete(first, "Disk full")
        self.assertIsNone(scheduler.busy)
        self.assertEqual(scheduler.error, "Disk full")
        self.assertIsNone(scheduler.choose(2, {1: request(1, 2)}))
        scheduler.request_update(1, 2)
        retry = scheduler.choose(3, {1: request(1, 3)})
        scheduler.complete(retry)
        self.assertIsNone(scheduler.error)
        self.assertIn(1, scheduler.known_saved)

    def test_unrelated_ack_cannot_release_single_writer_gate(self):
        scheduler = SaveScheduler()
        first = scheduler.choose(1, {1: request(1, 1)})
        scheduler.complete(request(2, 1))
        self.assertIs(scheduler.busy, first)
        scheduler.complete(first)
        self.assertIsNone(scheduler.busy)


if __name__ == "__main__":
    unittest.main()
