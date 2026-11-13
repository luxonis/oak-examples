"""Calibration controls and results are tested through real host queues."""

import time
import unittest
from threading import Event
from unittest.mock import patch

import depthai as dai
import numpy as np
from device_lookup import setUpModule, tearDownModule  # noqa: F401
from pydantic import ValidationError
from test_calibration_controller import GeometryScene, HostSource

from solutions_sdk.box_measurement import (
    CalibrationOutcome,
    PlaneCalibrationConfig,
    SupportPlane,
    SupportPlaneCalibrationControl,
    SupportPlaneCalibrationResult,
    SupportPlaneCalibrator,
    SupportPlaneVerificationResult,
)


class CalibrationValuesTests(unittest.TestCase):
    def test_configuration_is_immutable_and_controls_are_messages(self):
        config = PlaneCalibrationConfig()
        self.assertEqual(config.distance_threshold_mm, 10.0)
        self.assertEqual(config.ransac_sample_points, 3)
        with self.assertRaises(ValidationError):
            config.max_plane_passes = 1  # type: ignore[misc]
        self.assertIsNotNone(SupportPlaneCalibrationControl.start())
        self.assertIsNotNone(SupportPlaneCalibrationControl.stop())
        self.assertIsNotNone(SupportPlaneCalibrationControl.reset())
        result = SupportPlaneCalibrationResult(
            CalibrationOutcome.CANCELLED, [], "Stopped"
        )
        self.assertEqual(result.candidates, ())

    def test_each_control_carries_exactly_one_immutable_command(self):
        commands = SupportPlaneCalibrationControl.Commands
        self.assertIsInstance(
            SupportPlaneCalibrationControl.start().command, commands.Start
        )
        self.assertIsInstance(
            SupportPlaneCalibrationControl.stop().command, commands.Stop
        )
        self.assertIsInstance(
            SupportPlaneCalibrationControl.reset().command, commands.Reset
        )
        command = SupportPlaneCalibrationControl.start().command
        with self.assertRaises(ValidationError):
            command.extra = True  # type: ignore[attr-defined]

    def test_message_fields_cannot_be_reassigned(self):
        plane = SupportPlane(normal=(0, 0, 1), offset_mm=-1000)
        messages = {
            SupportPlaneCalibrationControl.start(): ("command",),
            SupportPlaneCalibrationResult(
                CalibrationOutcome.SUCCEEDED, [plane], "found"
            ): ("outcome", "candidates", "info"),
            SupportPlaneVerificationResult(plane, 3.0, True): (
                "plane",
                "gravity_angle_deg",
                "accepted",
            ),
        }
        for message, fields in messages.items():
            for field in fields:
                with self.subTest(field=field), self.assertRaises(AttributeError):
                    setattr(message, field, None)

    def test_result_candidates_are_a_tuple(self):
        plane = SupportPlane(normal=(0, 0, 1), offset_mm=-1000)
        candidates = [plane]
        result = SupportPlaneCalibrationResult(
            CalibrationOutcome.SUCCEEDED, candidates, "found"
        )
        candidates.append(plane)
        self.assertEqual(result.candidates, (plane,))

    def test_configuration_rejects_wrong_types_and_bad_values(self):
        for name in (
            "ransac_sample_points",
            "ransac_max_iterations",
            "max_plane_passes",
        ):
            for value in (3.5, "three", None, 0, -1):
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaises(ValidationError),
                ):
                    PlaneCalibrationConfig(**{name: value})
        for name in (
            "distance_threshold_mm",
            "min_inlier_ratio",
            "voxel_size_mm",
            "max_gravity_angle_deg",
            "merge_distance_threshold_mm",
        ):
            for value in ("one", None, float("nan"), -1.0):
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaises(ValidationError),
                ):
                    PlaneCalibrationConfig(**{name: value})
        for name, value in (
            ("ransac_sample_points", 2),
            ("min_inlier_ratio", 1.5),
            ("max_gravity_angle_deg", 90),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(
                ValidationError
            ):
                PlaneCalibrationConfig(**{name: value})
        self.assertEqual(PlaneCalibrationConfig(voxel_size_mm=30).voxel_size_mm, 30)

    def test_build_rejects_wrong_point_cloud_size_types_and_values(self):
        pipeline = dai.Pipeline(False)
        source = pipeline.create(HostSource)
        for size in [(0, 48), (64, -1), (64,)]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                pipeline.create(SupportPlaneCalibrator).build(
                    source.out, source.out, size
                )
        for size in [(64.0, 48), (True, True), ("64", 48)]:
            with self.subTest(size=size), self.assertRaises(TypeError):
                pipeline.create(SupportPlaneCalibrator).build(
                    source.out, source.out, size
                )

    def test_controls_reject_unknown_commands(self):
        for command in ("start", None, object()):
            with self.assertRaises(TypeError):
                SupportPlaneCalibrationControl(command)  # type: ignore[arg-type]

    def test_outcomes_are_their_string_values(self):
        self.assertEqual(CalibrationOutcome.SUCCEEDED, "succeeded")
        self.assertEqual(CalibrationOutcome.FAILED, "failed")
        self.assertEqual(CalibrationOutcome.CANCELLED, "cancelled")

    def test_results_reject_unknown_outcomes(self):
        with self.assertRaises(TypeError):
            SupportPlaneCalibrationResult("cancelled", [])  # type: ignore[arg-type]


class CalibratorPipeline(unittest.TestCase):
    """Real host queues around one calibrator; holds no tests itself."""

    config = PlaneCalibrationConfig(max_plane_passes=3)

    def setUp(self):
        self.pipeline = dai.Pipeline(False)
        cloud_source = self.pipeline.create(HostSource)
        imu_source = self.pipeline.create(HostSource)
        self.clouds = cloud_source.input.createInputQueue()
        self.imus = imu_source.input.createInputQueue()
        self.node = self.pipeline.create(SupportPlaneCalibrator).build(
            point_cloud=cloud_source.out,
            imu=imu_source.out,
            point_cloud_size=(20, 20),
            config=self.config,
        )
        self.controls = self.node.control_input.createInputQueue()
        self.results = self.node.out.createOutputQueue()
        self.verifications = self.node.verification_out.createOutputQueue()
        self.pipeline.start()

    def tearDown(self):
        self.pipeline.stop()
        self.pipeline.wait()

    def result(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.results.tryGet()
            if result is not None:
                return result
            time.sleep(0.005)
        self.fail("Calibration did not emit a terminal result")

    def gravity(self):
        msg = dai.IMUData()
        packet = dai.IMUPacket()
        packet.acceleroMeter.x = 0
        packet.acceleroMeter.y = 0
        packet.acceleroMeter.z = -9.8
        msg.packets = [packet]
        self.imus.send(msg)

    def plane_cloud(self, depth=1000):
        x, y = np.meshgrid(np.arange(20) * 40, np.arange(20) * 40)
        points = np.column_stack([x.ravel(), y.ravel(), np.full(400, depth)])
        msg = dai.PointCloudData()
        msg.setPoints(points.astype(np.float32))
        self.clouds.send(msg)

    def verification(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.verifications.tryGet()
            if result is not None:
                return result
            time.sleep(0.005)
        self.fail("Calibration did not emit a verification result")

    def verify(self, plane):
        self.controls.send(SupportPlaneCalibrationControl.verify(plane))
        return self.verification()


class CalibrationQueueTests(CalibratorPipeline):
    def test_first_qualifying_cloud_succeeds_only_after_gravity_arrives(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.plane_cloud()
        time.sleep(0.1)
        self.assertIsNone(self.results.tryGet())
        self.gravity()
        self.plane_cloud()
        result = self.result()
        self.assertEqual(result.outcome, CalibrationOutcome.SUCCEEDED)
        self.assertAlmostEqual(result.candidates[0].offset_mm, -1000, delta=1)
        self.assertAlmostEqual(result.candidates[0].normal[2], 1, delta=0.001)
        self.plane_cloud(depth=1500)
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())

    def test_cloud_sent_just_before_start_is_used_for_the_attempt(self):
        self.gravity()
        self.plane_cloud()
        # Let the cloud reach the idle calibrator before Start does.
        time.sleep(0.1)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())

    def test_searching_on_empty_cloud_or_recoverable_fit_miss_then_success(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud(depth=0)
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())
        scene = GeometryScene([])
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.plane_cloud()
            time.sleep(0.05)
            self.assertIsNone(self.results.tryGet())
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)

    def test_candidate_deduplication_and_rank_are_preserved(self):
        scene = GeometryScene(
            [
                ([0.0, 0.0, 1.0, -1500.0], 100),
                ([0.0, 0.0, 1.0, -1000.0], 150),
                ([0.0, 0.0, 1.0, -1010.0], 100),
            ]
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            result = self.result()
        self.assertEqual([p.offset_mm for p in result.candidates], [-1000, -1500])

    def test_equal_inlier_counts_rank_nearer_plane_first(self):
        scene = GeometryScene(
            [
                ([0.0, 0.0, 1.0, -1500.0], 100),
                ([0.0, 0.0, 1.0, -1000.0], 100),
            ]
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            result = self.result()
        self.assertEqual([p.offset_mm for p in result.candidates], [-1000, -1500])

    def test_gravity_and_offset_rejections_remain_searching(self):
        scene = GeometryScene(
            [
                ([0.0, 0.0, -1.0, -1000.0], 100),
                ([0.0, 0.0, 1.0, 1000.0], 100),
                ([1.0, 0.0, 0.0, -1000.0], 100),
            ]
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            time.sleep(0.05)
            self.assertIsNone(self.results.tryGet())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)

    def test_failure_is_terminal_and_reset_allows_retry(self):
        with patch(
            "open3d.geometry.PointCloud",
            GeometryScene([], error=ValueError("broken geometry")).cloud,
        ):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            result = self.result()
        self.assertEqual(result.outcome, CalibrationOutcome.FAILED)
        self.assertEqual(result.candidates, ())
        self.assertIn("broken geometry", result.info)
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)

    def test_message_that_is_not_a_point_cloud_fails_the_attempt(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.clouds.send(dai.Buffer())
        result = self.result()
        self.assertEqual(result.outcome, CalibrationOutcome.FAILED)
        self.assertIn("PointCloudData", result.info)

    def test_stop_during_fit_cancels_once_after_the_fit_and_returns_to_idle(self):
        entered, release = Event(), Event()
        # The fit keeps searching: its only plane faces away from gravity.
        scene = GeometryScene(
            [([0.0, 0.0, -1.0, -1000.0], 400)], entered=entered, release=release
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            self.assertTrue(entered.wait(5))
            self.controls.send(SupportPlaneCalibrationControl.stop())
            self.controls.send(SupportPlaneCalibrationControl.reset())
            time.sleep(0.05)
            # Stop waits for the current fit to finish.
            self.assertIsNone(self.results.tryGet())
            release.set()
            result = self.result()
        self.assertEqual(result.outcome, CalibrationOutcome.CANCELLED)
        self.assertEqual(result.candidates, ())
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)

    def test_fit_that_finds_a_plane_completes_before_stop_takes_effect(self):
        entered, release = Event(), Event()
        scene = GeometryScene(
            [([0.0, 0.0, 1.0, -1000.0], 400)], entered=entered, release=release
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            self.assertTrue(entered.wait(5))
            self.controls.send(SupportPlaneCalibrationControl.stop())
            release.set()
            result = self.result()
        self.assertEqual(result.outcome, CalibrationOutcome.SUCCEEDED)
        self.assertEqual([p.offset_mm for p in result.candidates], [-1000])
        # The late Stop finds no active attempt; success still requires reset.
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())

    def test_stopped_attempt_returns_to_idle_without_reset(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)

    def test_stop_after_completion_retains_success_and_still_requires_reset(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())
        # Unlike a stopped attempt, a completed one still requires reset.
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)

    def test_reset_leaves_unread_results_and_configuration_unchanged(self):
        scene = GeometryScene(
            [
                ([0.0, 0.0, 1.0, -1000.0], 100),
                ([0.0, 0.0, 1.0, -1500.0], 100),
                ([0.0, 0.0, 1.0, -2000.0], 100),
                ([0.0, 0.0, 1.0, -2500.0], 100),
            ]
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.gravity()
            self.plane_cloud()
            deadline = time.monotonic() + 5
            while not self.results.has() and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertTrue(self.results.has())
            self.controls.send(SupportPlaneCalibrationControl.reset())
            self.controls.send(SupportPlaneCalibrationControl.start())
            self.plane_cloud()
            # The unread success survives reset; both retries retain the three-pass config.
            first = self.result()
            second = self.result()
        self.assertEqual([p.offset_mm for p in first.candidates], [-1000, -1500, -2000])
        self.assertEqual(
            [p.offset_mm for p in second.candidates], [-1000, -1500, -2000]
        )

    def wait_for_pending_result(self):
        deadline = time.monotonic() + 5
        while not self.results.has() and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(self.results.has())

    def test_nonblocking_overflow_replaces_oldest_result(self):
        self.results.setMaxSize(1)
        self.results.setBlocking(False)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.wait_for_pending_result()
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        deadline = time.monotonic() + 5
        while (
            self.results.front().outcome is CalibrationOutcome.SUCCEEDED
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)
        self.assertIsNone(self.results.tryGet())

    def test_blocking_result_queue_retains_both_attempts(self):
        self.results.setMaxSize(1)
        self.results.setBlocking(True)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.wait_for_pending_result()
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)

    def test_start_is_accepted_while_cancelled_result_awaits_queue_space(self):
        self.results.setMaxSize(1)
        self.results.setBlocking(True)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.wait_for_pending_result()
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        # The cancelled result is blocked behind the unread success.
        self.controls.send(SupportPlaneCalibrationControl.start())
        time.sleep(0.05)
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)

    def test_stop_without_frames_emits_once_and_returns_to_idle(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())
        # Reset is a no-op while idle; the next start is accepted either way.
        self.controls.send(SupportPlaneCalibrationControl.reset())
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        self.assertEqual(self.result().outcome, CalibrationOutcome.CANCELLED)


def tilted_plane(angle_deg, offset_mm=-1000.0):
    angle = np.deg2rad(angle_deg)
    return SupportPlane(normal=(0.0, np.sin(angle), np.cos(angle)), offset_mm=offset_mm)


class VerificationTests(CalibratorPipeline):
    """Saved planes are judged against raw accelerometer gravity."""

    def test_plane_opposing_gravity_is_accepted_with_its_angle(self):
        self.gravity()
        plane = tilted_plane(3)
        result = self.verify(plane)
        self.assertIsInstance(result, SupportPlaneVerificationResult)
        self.assertEqual(result.plane, plane)
        self.assertTrue(result.accepted)
        self.assertAlmostEqual(result.gravity_angle_deg, 3, places=4)

    def test_plane_beyond_tolerance_is_rejected(self):
        self.gravity()
        self.assertTrue(self.verify(tilted_plane(6)).accepted)
        result = self.verify(tilted_plane(7))
        self.assertFalse(result.accepted)
        self.assertAlmostEqual(result.gravity_angle_deg, 7, places=4)

    def test_unnormalized_equation_is_judged_by_direction(self):
        self.gravity()
        self.assertTrue(
            self.verify(SupportPlane(normal=(0, 0, 3), offset_mm=-3000)).accepted
        )

    def test_plane_behind_the_camera_is_rejected(self):
        self.gravity()
        result = self.verify(tilted_plane(0, offset_mm=1000))
        self.assertFalse(result.accepted)
        self.assertAlmostEqual(result.gravity_angle_deg, 0, places=4)

    def test_opposite_sign_equation_of_an_accepted_plane_is_rejected(self):
        self.gravity()
        self.assertTrue(
            self.verify(SupportPlane(normal=(0, 0, 1), offset_mm=-1000)).accepted
        )
        result = self.verify(SupportPlane(normal=(0, 0, -1), offset_mm=1000))
        self.assertFalse(result.accepted)
        self.assertAlmostEqual(result.gravity_angle_deg, 180, places=4)

    def test_verify_before_imu_is_answered_by_the_first_sample(self):
        self.controls.send(SupportPlaneCalibrationControl.verify(tilted_plane(0)))
        time.sleep(0.1)
        self.assertIsNone(self.verifications.tryGet())
        self.gravity()
        self.assertTrue(self.verification().accepted)

    def test_each_verify_produces_one_result_in_order(self):
        planes = [tilted_plane(0), tilted_plane(7), tilted_plane(3)]
        for plane in planes:
            self.controls.send(SupportPlaneCalibrationControl.verify(plane))
        self.gravity()
        self.assertEqual([self.verification().plane for _ in planes], planes)
        self.gravity()
        time.sleep(0.05)
        self.assertIsNone(self.verifications.tryGet())

    def test_search_keeps_running_while_a_verify_is_handled(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.assertTrue(self.verify(tilted_plane(0)).accepted)
        self.assertIsNone(self.results.tryGet())
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)

    def test_verify_leaves_a_completed_attempt_awaiting_reset(self):
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.gravity()
        self.plane_cloud()
        self.assertEqual(self.result().outcome, CalibrationOutcome.SUCCEEDED)
        self.assertTrue(self.verify(tilted_plane(0)).accepted)
        self.controls.send(SupportPlaneCalibrationControl.start())
        self.controls.send(SupportPlaneCalibrationControl.stop())
        time.sleep(0.05)
        self.assertIsNone(self.results.tryGet())

    def test_verify_requires_a_support_plane(self):
        with self.assertRaises(ValidationError):
            SupportPlaneCalibrationControl.verify((0, 0, 1, -1000))  # type: ignore[arg-type]


class ConfiguredToleranceVerificationTests(CalibratorPipeline):
    config = PlaneCalibrationConfig(max_gravity_angle_deg=1)

    def test_verification_uses_the_built_tolerance(self):
        self.gravity()
        self.assertFalse(self.verify(tilted_plane(3)).accepted)
        self.assertTrue(self.verify(tilted_plane(0.5)).accepted)


if __name__ == "__main__":
    unittest.main()
