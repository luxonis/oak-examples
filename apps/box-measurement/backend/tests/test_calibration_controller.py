"""Application services coordinate native SDK controls/results and live previews."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import depthai as dai
import numpy as np
from box_measurement_harness import MeasurementPipeline
from test_support_plane_calibrator import HostSource

from services.support_plane_controller import SupportPlaneController
from solutions_sdk.box_measurement import (
    SupportPlane,
    SupportPlaneCalibrationControl,
    SupportPlaneCalibrator,
)


class CalibrationControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.flow = MeasurementPipeline()
        self.addCleanup(self.flow.close)
        self.pipeline = dai.Pipeline(False)
        cloud, imu = [self.pipeline.create(HostSource) for _ in range(2)]
        self.cloud_output = cloud.out
        self.clouds = cloud.input.createInputQueue()
        self.imus = imu.input.createInputQueue()
        self.calibrator = self.pipeline.create(SupportPlaneCalibrator).build(
            cloud.out, imu.out, (20, 20)
        )

    def build(self):
        self.controller = SupportPlaneController(self.calibrator, self.flow.measurer)
        self.pipeline.start()
        self.controller.start()
        self.addCleanup(self.pipeline.wait)
        self.addCleanup(self.pipeline.stop)
        self.addCleanup(self.controller.close)
        return self.controller

    def gravity(self, z=-9.8):
        msg = dai.IMUData()
        packet = dai.IMUPacket()
        packet.acceleroMeter.z = z
        msg.packets = [packet]
        return msg

    def stream(self):
        self.imus.send(self.gravity())
        x, y = np.meshgrid(np.arange(20) * 40, np.arange(20) * 40)
        cloud = dai.PointCloudData()
        cloud.setPoints(
            np.column_stack([x.ravel(), y.ravel(), np.full(400, 1000)]).astype(
                np.float32
            )
        )
        self.clouds.send(cloud)

    def until(self, predicate, stream=True):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            if stream:
                self.stream()
            time.sleep(0.005)
        self.assertTrue(predicate(), self.controller.get_status())

    def test_new_controller_starts_searching_with_no_support_plane(self):
        controller = self.build()
        self.assertEqual(controller.get_status()["state"], "SEARCHING")
        self.assertEqual(controller.get_status()["distance_offset_mm"], 0)
        self.assertIsNone(self.flow.measurer.getSupportPlane())

    def test_select_confirm_offset_then_recalibrate_clears_live_correction(self):
        controller = self.build()
        self.until(
            lambda: controller.get_status().get("state") == "AWAITING_CONFIRMATION"
        )
        self.assertTrue(controller.cycle_candidate(-1))
        self.assertTrue(controller.confirm_candidate())
        self.assertFalse(controller.confirm_candidate())
        self.assertEqual(controller.get_status()["state"], "CONFIRMED")
        self.flow.send()
        self.assertAlmostEqual(
            self.flow.receive().items[0].dimensions.height_mm, 100, delta=2
        )
        controller.set_distance_offset(20)
        self.flow.send()
        self.assertAlmostEqual(
            self.flow.receive().items[0].dimensions.height_mm, 120, delta=2
        )
        controller.request_recalibration()
        self.assertEqual(controller.get_status()["state"], "SEARCHING")
        self.assertEqual(controller.get_status()["distance_offset_mm"], 0)
        self.assertIsNone(self.flow.measurer.getSupportPlane())

    def test_failure_rejects_stale_confirmation_and_retry_clears_error(self):
        from test_support_plane_calibrator import GeometryScene

        controller = self.build()
        with patch(
            "open3d.geometry.PointCloud",
            GeometryScene([], error=ValueError("bad sensor processing")).cloud,
        ):
            self.until(lambda: "error" in controller.get_status())
        self.assertIn("bad sensor processing", controller.get_status()["error"])
        self.assertFalse(controller.confirm_candidate())
        self.assertFalse(controller.cycle_candidate())
        controller.request_recalibration()
        self.assertNotIn("error", controller.get_status())
        self.until(
            lambda: controller.get_status().get("state") == "AWAITING_CONFIRMATION"
        )

    def test_repeated_restart_during_fit_is_responsive_and_ignores_old_candidates(self):
        from threading import Event

        from test_support_plane_calibrator import GeometryScene

        entered, release = Event(), Event()
        self.addCleanup(release.set)
        controller = self.build()
        scene = GeometryScene(
            [([0, 0, 1, -2000], 400)], entered=entered, release=release
        )
        with patch("open3d.geometry.PointCloud", scene.cloud):
            self.until(entered.is_set)
            begin = time.monotonic()
            controller.request_recalibration()
            controller.request_recalibration()
            controller.request_recalibration()
            self.assertLess(time.monotonic() - begin, 0.2)
            self.assertEqual(controller.get_status()["state"], "SEARCHING")
            self.assertFalse(controller.confirm_candidate())
        # Release outside the patch: the restarted attempt may take a cloud sent
        # before it started, and must fit it with real geometry.
        release.set()
        # No further clouds are sent: cancelled result must still be consumed.
        time.sleep(0.1)
        self.until(
            lambda: controller.get_status().get("state") == "AWAITING_CONFIRMATION"
        )
        self.assertAlmostEqual(controller.get_status()["camera_distance_mm"], 1000)

    def test_close_detaches_gated_old_result_without_waiting_for_fit(self):
        from threading import Event

        from test_support_plane_calibrator import GeometryScene

        entered, release = Event(), Event()
        self.addCleanup(release.set)
        controller = self.build()
        with patch(
            "open3d.geometry.PointCloud",
            GeometryScene(
                [([0, 0, 1, -2000], 400)], entered=entered, release=release
            ).cloud,
        ):
            self.until(entered.is_set)
            begin = time.monotonic()
            controller.close()
            self.assertLess(time.monotonic() - begin, 0.2)
            replacement = SupportPlane(normal=(0, 0, 1), offset_mm=-900)
            self.flow.measurer.setSupportPlane(replacement)
            release.set()
            time.sleep(0.1)
            self.assertEqual(self.flow.measurer.getSupportPlane(), replacement)
            self.assertIn("error", controller.get_status())
            self.assertFalse(controller.confirm_candidate())

    def test_preview_is_requested_live_orange_then_green_and_moves_with_correction(
        self,
    ):
        from depthai_pipeline.node.support_plane_preview import SupportPlanePreview

        self.controller = SupportPlaneController(self.calibrator, self.flow.measurer)
        preview = self.pipeline.create(SupportPlanePreview).build(
            self.cloud_output, (20, 20), self.controller
        )
        output = preview.out.createOutputQueue()
        self.pipeline.start()
        self.controller.start()
        self.addCleanup(self.pipeline.wait)
        self.addCleanup(self.pipeline.stop)
        self.addCleanup(self.controller.close)
        self.until(
            lambda: self.controller.get_status().get("state") == "AWAITING_CONFIRMATION"
        )
        self.assertIsNone(output.tryGet())
        self.controller.set_preview_active(True)
        # Dense cells survive the preview decimation and grid occupancy filter.
        x, y = np.meshgrid(np.linspace(0, 200, 120), np.linspace(0, 200, 120))
        points = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 1000)]).astype(
            np.float32
        )
        colors = np.full((len(points), 4), (20, 30, 40, 255), dtype=np.uint8)
        cloud = dai.PointCloudData()
        cloud.setPointsRGB(points, colors)

        def receive():
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                result = output.tryGet()
                if result is not None:
                    return result
                self.clouds.send(cloud)
                time.sleep(0.01)
            self.fail("No live preview")

        pending = receive()
        _, pending_colors = pending.getPointsRGB()
        self.assertTrue(np.any(np.all(pending_colors == (255, 140, 0, 255), axis=1)))
        self.assertTrue(self.controller.confirm_candidate())
        self.controller.set_distance_offset(20)
        while output.tryGet() is not None:
            pass
        active = receive()
        active_points, active_colors = active.getPointsRGB()
        grid = np.all(active_colors == (0, 255, 0, 255), axis=1)
        self.assertTrue(grid.any())
        self.assertTrue(np.allclose(active_points[grid, 2], 1020, atol=0.1))
        self.assertGreater(len(receive().getPoints()), 0)
        self.controller.set_preview_active(False)

    def services(self):
        from test_confidence_service import RemoteServices

        from app import App
        from services.application_logging import ApplicationLoggingService
        from services.event_export import archive_storage
        from settings import settings_store

        for item in (
            patch.object(dai, "RemoteConnection", RemoteServices),
            patch.object(settings_store, "STORAGE_BASE_PATH", self.directory.name),
            patch.object(archive_storage, "STORAGE_BASE_PATH", self.directory.name),
        ):
            item.start()
            self.addCleanup(item.stop)
        logging = ApplicationLoggingService(Path(self.directory.name))
        self.addCleanup(logging.handler.close)
        app = App(logging)
        app._support_plane = self.controller
        return app.visualizer.services

    def test_services_report_failure_retry_select_confirm_offset_and_preview(self):
        from test_support_plane_calibrator import GeometryScene

        self.build()
        services = self.services()
        with patch(
            "open3d.geometry.PointCloud",
            GeometryScene([], error=ValueError("sensor failure")).cloud,
        ):
            self.until(
                lambda: "error" in services["getSupportPlaneCalibrationStatus"]({})
            )
        self.assertIn(
            "sensor failure", services["getSupportPlaneCalibrationStatus"]({})["error"]
        )
        self.assertIn("error", services["confirmSupportPlane"]({}))
        self.assertEqual(services["retrySupportPlaneCalibration"]({}), {})
        self.until(
            lambda: services["getSupportPlaneCalibrationStatus"]({}).get("state")
            == "AWAITING_CONFIRMATION"
        )
        self.assertIn(
            "error", services["setSupportPlaneDistanceOffset"]({"offset_mm": 20})
        )
        self.assertEqual(services["selectSupportPlaneCandidate"]({"direction": -1}), {})
        self.assertEqual(services["confirmSupportPlane"]({}), {})
        self.assertEqual(
            services["getSupportPlaneCalibrationStatus"]({})["state"], "CONFIRMED"
        )
        self.assertEqual(
            services["setSupportPlaneDistanceOffset"]({"offset_mm": 20}), {}
        )
        self.assertAlmostEqual(self.flow.measurer.getSupportPlane().offset_mm, -1020)
        self.assertEqual(services["setSupportPlanePreviewActive"]({"active": True}), {})
        self.assertIn("error", services["confirmSupportPlane"]({}))
        self.assertEqual(services["retrySupportPlaneCalibration"]({}), {})
        self.assertIsNone(self.flow.measurer.getSupportPlane())
        self.assertEqual(
            services["getSupportPlaneCalibrationStatus"]({})["state"], "SEARCHING"
        )


class ResultEndpoint(dai.node.ThreadedHostNode):
    """Inject public SDK results and observe controls at native queue boundaries."""

    def __init__(self):
        super().__init__()
        self.control_input = self.createInput()
        self.results = self.createInput()
        self.out = self.createOutput()
        self.commands = self.createOutput()

    def run(self):
        from threading import Event

        pause = Event()
        try:
            while self.isRunning():
                control = self.control_input.tryGet()
                if control is not None:
                    self.commands.send(control)
                result = self.results.tryGet()
                if result is not None:
                    self.out.send(result)
                pause.wait(0.001)
        except dai.MessageQueue.QueueException:
            return


class CalibrationSequencingTests(unittest.TestCase):
    def start_session(self):
        """One app start: a fresh measurer, calibrator endpoint and controller."""
        flow = MeasurementPipeline()
        self.addCleanup(flow.close)
        pipeline = dai.Pipeline(False)
        endpoint = pipeline.create(ResultEndpoint)
        results = endpoint.results.createInputQueue()
        controls = endpoint.commands.createOutputQueue()
        controller = SupportPlaneController(endpoint, flow.measurer)
        pipeline.start()
        self.addCleanup(pipeline.wait)
        self.addCleanup(pipeline.stop)
        self.addCleanup(controller.close)
        controller.start()
        return flow, pipeline, results, controls, controller

    def next_command_type(self, controls):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            item = controls.tryGet()
            if item is not None:
                return type(item.command)
            time.sleep(0.001)
        self.fail("Missing calibration control")

    def test_every_start_searches_even_after_a_previous_start_confirmed(self):
        from solutions_sdk.box_measurement import (
            CalibrationOutcome,
            SupportPlaneCalibrationResult,
        )

        commands = SupportPlaneCalibrationControl.Commands
        _, pipeline, results, controls, controller = self.start_session()
        self.assertIs(self.next_command_type(controls), commands.Start)
        results.send(
            SupportPlaneCalibrationResult(
                CalibrationOutcome.SUCCEEDED,
                [SupportPlane(normal=(0, 0, 1), offset_mm=-1000)],
                "Found",
            )
        )
        deadline = time.monotonic() + 3
        while (
            controller.get_status()["state"] != "AWAITING_CONFIRMATION"
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        self.assertTrue(controller.confirm_candidate())
        controller.set_distance_offset(20)
        controller.close()
        pipeline.stop()
        pipeline.wait()

        flow, _, _, controls, controller = self.start_session()
        self.assertEqual(controller.get_status()["state"], "SEARCHING")
        self.assertEqual(controller.get_status()["distance_offset_mm"], 0)
        self.assertIsNone(flow.measurer.getSupportPlane())
        self.assertIs(self.next_command_type(controls), commands.Start)

    def test_queued_old_success_is_discarded_before_reset_start_and_selection(self):
        from solutions_sdk.box_measurement import (
            CalibrationOutcome,
            SupportPlaneCalibrationResult,
        )

        flow = MeasurementPipeline()
        self.addCleanup(flow.close)
        pipeline = dai.Pipeline(False)
        endpoint = pipeline.create(ResultEndpoint)
        results = endpoint.results.createInputQueue()
        controls = endpoint.commands.createOutputQueue()
        controller = SupportPlaneController(endpoint, flow.measurer)
        pipeline.start()
        self.addCleanup(pipeline.wait)
        self.addCleanup(pipeline.stop)
        self.addCleanup(controller.close)
        # Initial idle retry must not wait for an attempt that never existed.
        controller.request_recalibration()
        controller.start()

        def next_command_type():
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                item = controls.tryGet()
                if item is not None:
                    return type(item.command)
                time.sleep(0.001)
            self.fail("Missing calibration control")

        commands = SupportPlaneCalibrationControl.Commands
        self.assertIs(next_command_type(), commands.Start)
        controller.request_recalibration()
        controller.request_recalibration()
        self.assertIs(next_command_type(), commands.Stop)
        results.send(
            SupportPlaneCalibrationResult(
                CalibrationOutcome.SUCCEEDED,
                [SupportPlane(normal=(0, 0, 1), offset_mm=-2000)],
                "Old queued success",
            )
        )
        self.assertIs(next_command_type(), commands.Reset)
        self.assertIs(next_command_type(), commands.Start)
        self.assertEqual(controller.get_status()["state"], "SEARCHING")
        self.assertFalse(controller.confirm_candidate())
        results.send(
            SupportPlaneCalibrationResult(
                CalibrationOutcome.SUCCEEDED,
                [SupportPlane(normal=(0, 0, 1), offset_mm=-1000), SupportPlane(normal=(0, 0, 1), offset_mm=-1500)],
                "New success",
            )
        )
        deadline = time.monotonic() + 3
        while (
            controller.get_status()["state"] != "AWAITING_CONFIRMATION"
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        self.assertEqual(controller.get_status()["candidate_count"], 2)
        self.assertTrue(controller.cycle_candidate(-1))
        self.assertEqual(controller.get_status()["camera_distance_mm"], 1500)
        self.assertTrue(controller.confirm_candidate())
        # Completed and consumed result needs no stop/wait cycle.
        controller.request_recalibration()
        self.assertIs(next_command_type(), commands.Reset)
        self.assertIs(next_command_type(), commands.Start)
