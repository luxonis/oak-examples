from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import cv2

from utils.depthai_path import configure_depthai_path

configure_depthai_path()

import depthai as dai

from utils.arguments import initialize_argparser
from utils.ffc_calibration import (
    CalibrationDashboardNode,
    CoverageOverlayNode,
    DepthPreviewNode,
    FfcCalibrationApp,
    StereoPair,
    format_socket,
)

BASELINE_SERVICE = "FFC Set Baselines"
SOCKET_SERVICE = "FFC Set Sockets"
FLASH_SERVICE = "FFC Flash Calibration"
STATE_SERVICE = "FFC State"
PAIR_SERVICE = "FFC Select Pair"
NAVIGATE_SERVICE = "FFC Navigate"
DEPTH_CURSOR_SERVICE = "FFC Depth Cursor"
DEPTH_RANGE_SERVICE = "FFC Depth Range"
DEPTH_STATE_SERVICE = "FFC Depth State"


@dataclass(frozen=True)
class TopicToggles:
    dashboard: bool = True
    left: bool = True
    right: bool = True
    depth: bool = True


@dataclass
class FfcPairStats:
    label: str
    left: str
    right: str
    baseline_cm: float
    translation: list[float]
    entered_baseline_cm: float | None = None


@dataclass(frozen=True)
class NavigationAction:
    stage: str


class FfcFrontendState:
    def __init__(self, app: FfcCalibrationApp, topic_toggles: TopicToggles):
        self._app = app
        self._topic_toggles = topic_toggles
        self._lock = threading.Lock()
        self._stage = "socket_select"
        self._status = "Select sockets to include."
        self._socket_ready = False
        self._baseline_ready = False
        self._baselines: dict[str, float] = {}
        self._pairs: list[FfcPairStats] = []
        self._selected_pair_idx = 0
        self._requested_pair_idx: int | None = None
        self._flash_requested = False
        self._flash_status = ""
        self._navigation_request: NavigationAction | None = None
        self._depth_preview = {
            "lock": threading.Lock(),
            "min_distance_mm": 300,
            "max_distance_mm": 5000,
            "hover_x": None,
            "hover_y": None,
            "probe_mm": None,
            "frame_width": 0,
            "frame_height": 0,
        }

    def socket_options(self) -> list[dict]:
        return [self._feature_to_dict(feature) for feature in self._app.camera_features]

    def baseline_fields(self) -> list[dict]:
        return [
            {
                "key": self._baseline_key(src, dest),
                "left": format_socket(src),
                "right": format_socket(dest),
            }
            for src, dest in self._app.baseline_pairs
        ]

    def recommended_baseline_fields(self) -> list[dict]:
        return [
            {
                "key": self._baseline_key(src, dest),
                "left": format_socket(src),
                "right": format_socket(dest),
            }
            for src, dest in self._app._recommended_baseline_pairs(self._app.sockets)
        ]

    def set_stage(self, stage: str, status: str) -> None:
        with self._lock:
            self._stage = stage
            self._status = status

    def reject_baselines(self, status: str) -> None:
        with self._lock:
            self._baseline_ready = False
            self._stage = "baseline"
            self._status = status

    def wait_for_baselines(self) -> dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float]:
        while True:
            with self._lock:
                if self._navigation_request is not None:
                    raise RuntimeError(f"NAVIGATE:{self._navigation_request.stage}")
                if self._baseline_ready:
                    return {
                        self._socket_key_to_pair(key): value
                        for key, value in self._baselines.items()
                    }
            time.sleep(0.05)

    def wait_for_socket_selection(self) -> None:
        while True:
            with self._lock:
                if self._navigation_request is not None:
                    raise RuntimeError(f"NAVIGATE:{self._navigation_request.stage}")
                if self._socket_ready:
                    return
            time.sleep(0.05)

    def handle_set_sockets(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        labels = payload.get("sockets", [])
        if not isinstance(labels, list):
            return {"ok": False, "error": "Expected sockets list"}

        sockets_by_label = {
            format_socket(socket): socket
            for socket in self._app.all_sockets
        }
        try:
            sockets = [sockets_by_label[str(label)] for label in labels]
            self._app.select_sockets(sockets)
        except KeyError as exc:
            return {"ok": False, "error": f"Unknown socket {exc}"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        with self._lock:
            self._socket_ready = True
            self._stage = "baseline"
            self._status = "Choose baseline links, then enter distances."
            self._baselines = {}
            self._baseline_ready = False
        return {"ok": True}

    def handle_set_baselines(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        values = payload.get("baselines", payload)
        paths = payload.get("paths")
        if paths is not None:
            try:
                self._app.select_baseline_pairs(self._parse_baseline_paths(paths))
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}

        parsed: dict[str, float] = {}
        for field in self.baseline_fields():
            raw = values.get(field["key"])
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return {"ok": False, "error": f"Invalid baseline for {field['left']} -> {field['right']}"}
            if value == 0:
                return {"ok": False, "error": f"Baseline must be non-zero for {field['left']} -> {field['right']}"}
            parsed[field["key"]] = value

        with self._lock:
            self._baselines = parsed
            self._baseline_ready = True
            self._stage = "calibrating"
            self._status = "Starting dynamic calibration."
        return {"ok": True}

    def update_pairs(
        self,
        pairs: list[StereoPair],
        calibration: dai.CalibrationHandler,
        entered_baselines: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float],
        selected_idx: int,
    ) -> None:
        stats: list[FfcPairStats] = []
        for pair in pairs:
            tvec = np.asarray(
                calibration.getCameraTranslationVector(pair.left, pair.right, False)
            ).reshape(-1)
            entered = entered_baselines.get((pair.left, pair.right))
            if entered is None:
                entered = entered_baselines.get((pair.right, pair.left))
            stats.append(
                FfcPairStats(
                    label=pair.label(),
                    left=format_socket(pair.left),
                    right=format_socket(pair.right),
                    baseline_cm=float(np.linalg.norm(tvec)),
                    translation=[float(v) for v in tvec[:3]],
                    entered_baseline_cm=entered,
                )
            )
        with self._lock:
            self._pairs = stats
            self._selected_pair_idx = selected_idx
            self._stage = "preview"
            self._status = "Select a stereo pair in the browser."

    def handle_select_pair(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        try:
            idx = int(payload.get("index"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Missing pair index"}
        with self._lock:
            if idx < 0 or idx >= len(self._pairs):
                return {"ok": False, "error": "Pair index out of range"}
            self._requested_pair_idx = idx
            self._selected_pair_idx = idx
        return {"ok": True}

    def consume_pair_request(self) -> int | None:
        with self._lock:
            requested = self._requested_pair_idx
            self._requested_pair_idx = None
            return requested

    def handle_flash_request(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        if payload.get("confirm") is not True:
            return {"ok": True, "ignored": True}
        with self._lock:
            self._flash_requested = True
            self._flash_status = "Flash requested."
        return {"ok": True}

    def handle_navigate(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        stage = str(payload.get("stage", "")).strip()
        if stage not in {"socket_select", "baseline"}:
            return {"ok": False, "error": "Unsupported navigation stage"}

        with self._lock:
            self._navigation_request = NavigationAction(stage=stage)
            self._requested_pair_idx = None
            self._flash_requested = False

            if stage == "socket_select":
                self._socket_ready = False
                self._baseline_ready = False
                self._baselines = {}
                self._pairs = []
                self._selected_pair_idx = 0
                self._flash_status = ""
                self._app.select_sockets(self._app.all_sockets)
                self._stage = "socket_select"
                self._status = "Select sockets to include."
            else:
                self._baseline_ready = False
                self._pairs = []
                self._selected_pair_idx = 0
                self._flash_status = ""
                self._stage = "baseline"
                self._status = "Choose baseline links, then enter distances."
        return {"ok": True}

    def consume_flash_request(self) -> bool:
        with self._lock:
            requested = self._flash_requested
            self._flash_requested = False
            return requested

    def consume_navigation_request(self) -> NavigationAction | None:
        with self._lock:
            action = self._navigation_request
            self._navigation_request = None
            return action

    def set_flash_status(self, status: str) -> None:
        with self._lock:
            self._flash_status = status

    def handle_get_state(self, _req=None) -> dict:
        with self._lock:
            with self._depth_preview["lock"]:
                depth_state = {
                    "minDistanceMm": int(self._depth_preview["min_distance_mm"]),
                    "maxDistanceMm": int(self._depth_preview["max_distance_mm"]),
                    "probeMm": (
                        None
                        if self._depth_preview["probe_mm"] is None
                        else float(self._depth_preview["probe_mm"])
                    ),
                    "frameWidth": int(self._depth_preview["frame_width"]),
                    "frameHeight": int(self._depth_preview["frame_height"]),
                }
            return {
                "ok": True,
                "stage": self._stage,
                "status": self._status,
                "socketOptions": self.socket_options(),
                "selectedSockets": [format_socket(socket) for socket in self._app.sockets],
                "baselineFields": self.baseline_fields(),
                "recommendedBaselineFields": self.recommended_baseline_fields(),
                "baselines": dict(self._baselines),
                "pairs": [pair.__dict__ for pair in self._pairs],
                "selectedPairIndex": self._selected_pair_idx,
                "flashStatus": self._flash_status,
                "depthPreview": depth_state,
                "streamTopics": [
                    topic
                    for enabled, topic in (
                        (self._topic_toggles.dashboard, "Dashboard"),
                        (self._topic_toggles.left, "Left"),
                        (self._topic_toggles.right, "Right"),
                        (self._topic_toggles.depth, "Depth"),
                    )
                    if enabled
                ],
            }

    def handle_set_depth_cursor(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        x = payload.get("x")
        y = payload.get("y")
        frame_width = payload.get("frameWidth")
        frame_height = payload.get("frameHeight")
        with self._depth_preview["lock"]:
            if x is None or y is None:
                self._depth_preview["hover_x"] = None
                self._depth_preview["hover_y"] = None
                self._depth_preview["probe_mm"] = None
                return {"ok": True}
            try:
                px = float(x)
                py = float(y)
            except (TypeError, ValueError):
                return {"ok": False, "error": "Invalid cursor coordinates"}
            width = int(self._depth_preview["frame_width"] or 0)
            height = int(self._depth_preview["frame_height"] or 0)
            if frame_width is not None:
                try:
                    width = max(width, int(frame_width))
                except (TypeError, ValueError):
                    pass
            if frame_height is not None:
                try:
                    height = max(height, int(frame_height))
                except (TypeError, ValueError):
                    pass
            if 0.0 <= px <= 1.0 and width > 0:
                px *= max(width - 1, 0)
            if 0.0 <= py <= 1.0 and height > 0:
                py *= max(height - 1, 0)
            self._depth_preview["hover_x"] = int(round(px))
            self._depth_preview["hover_y"] = int(round(py))
        return {"ok": True}

    def handle_set_depth_range(self, req=None) -> dict:
        payload = req if isinstance(req, dict) else {}
        try:
            min_distance_mm = int(payload.get("minDistanceMm"))
            max_distance_mm = int(payload.get("maxDistanceMm"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Invalid depth range"}
        min_distance_mm = max(100, min_distance_mm)
        max_distance_mm = min(20000, max_distance_mm)
        if min_distance_mm >= max_distance_mm:
            return {"ok": False, "error": "Depth min must be smaller than max"}
        with self._depth_preview["lock"]:
            self._depth_preview["min_distance_mm"] = min_distance_mm
            self._depth_preview["max_distance_mm"] = max_distance_mm
        return {"ok": True}

    def handle_get_depth_state(self, _req=None) -> dict:
        with self._depth_preview["lock"]:
            return {
                "ok": True,
                "minDistanceMm": int(self._depth_preview["min_distance_mm"]),
                "maxDistanceMm": int(self._depth_preview["max_distance_mm"]),
                "probeMm": (
                    None
                    if self._depth_preview["probe_mm"] is None
                    else float(self._depth_preview["probe_mm"])
                ),
                "frameWidth": int(self._depth_preview["frame_width"]),
                "frameHeight": int(self._depth_preview["frame_height"]),
            }

    def _baseline_key(self, src: dai.CameraBoardSocket, dest: dai.CameraBoardSocket) -> str:
        return f"{format_socket(src)}__{format_socket(dest)}"

    def _socket_key_to_pair(self, key: str) -> tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]:
        left_label, right_label = key.split("__", 1)
        sockets_by_label = {format_socket(socket): socket for socket in self._app.sockets}
        return sockets_by_label[left_label], sockets_by_label[right_label]

    def _parse_baseline_paths(self, paths) -> list[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]]:
        if not isinstance(paths, list):
            raise ValueError("Expected baseline paths list")

        sockets_by_label = {format_socket(socket): socket for socket in self._app.sockets}
        pairs: list[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]] = []
        for path in paths:
            if not isinstance(path, dict):
                raise ValueError("Each baseline path must be an object")
            try:
                src = sockets_by_label[str(path["left"])]
                dest = sockets_by_label[str(path["right"])]
            except KeyError as exc:
                raise ValueError(f"Unknown baseline socket {exc}") from exc
            pairs.append((src, dest))
        return pairs

    def _feature_to_dict(self, feature) -> dict:
        def value(name: str, default=None):
            item = getattr(feature, name, default)
            if isinstance(item, (str, int, float, bool)) or item is None:
                return item
            if isinstance(item, (list, tuple)):
                return [str(entry) for entry in item]
            return str(item)

        return {
            "socket": format_socket(feature.socket),
            "sensorName": value("sensorName", ""),
            "width": value("width", -1),
            "height": value("height", -1),
            "orientation": value("orientation", ""),
            "supportedTypes": value("supportedTypes", []),
            "hasAutofocus": value("hasAutofocus", False),
            "hasAutofocusIC": value("hasAutofocusIC", False),
            "name": value("name", ""),
            "additionalNames": value("additionalNames", []),
            "calibrationResolution": value("calibrationResolution", None),
        }


def _device_summary(device_info: dai.DeviceInfo) -> str:
    protocol = getattr(getattr(device_info, "protocol", None), "name", "unknown")
    return f"{device_info.getDeviceId()} [{protocol}]"


def _choose_device(requested_device: str | None) -> str | None:
    if requested_device:
        print(f"Using requested device: {requested_device}")
        return requested_device

    available_devices = dai.Device.getAllAvailableDevices()
    if not available_devices:
        print("No DepthAI devices found.")
        return None

    if len(available_devices) == 1:
        selected = available_devices[0].getDeviceId()
        print(f"Found one device: {_device_summary(available_devices[0])}")
        return selected

    print("Available devices:")
    for idx, device_info in enumerate(available_devices, start=1):
        print(f"  {idx}. {_device_summary(device_info)}")

    while True:
        choice = input("Select a device by number, or press q to quit: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return None
        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        index = int(choice) - 1
        if 0 <= index < len(available_devices):
            return available_devices[index].getDeviceId()

        print("Selection out of range.")


def _make_visualizer(http_port: int, ws_port: int) -> tuple[dai.RemoteConnection, int]:
    last_error: Exception | None = None
    for candidate in range(ws_port, ws_port + 20):
        try:
            return (
                dai.RemoteConnection(
                    httpPort=http_port,
                    webSocketPort=candidate,
                    serveFrontend=False,
                ),
                candidate,
            )
        except RuntimeError as exc:
            last_error = exc
            if "websocket server" not in str(exc).lower() and "listen on port" not in str(exc).lower():
                raise
            print(f"WebSocket port {candidate} is busy, trying {candidate + 1}...")

    raise RuntimeError(
        f"Failed to initialize websocket server on ports {ws_port}-{ws_port + 19}"
    ) from last_error


def _reset_topics(visualizer: dai.RemoteConnection, topics: list[str]) -> None:
    for topic in topics:
        try:
            visualizer.removeTopic(topic)
        except Exception:
            pass


def _add_enabled_topics(
    visualizer: dai.RemoteConnection,
    toggles: TopicToggles,
    dashboard_out=None,
    left_out=None,
    right_out=None,
    depth_out=None,
) -> None:
    if toggles.dashboard and dashboard_out is not None:
        visualizer.addTopic("Dashboard", dashboard_out, "dashboard")
    if toggles.left and left_out is not None:
        visualizer.addTopic("Left", left_out, "images")
    if toggles.right and right_out is not None:
        visualizer.addTopic("Right", right_out, "images")
    if toggles.depth and depth_out is not None:
        visualizer.addTopic("Depth", depth_out, "depth")


def _selected_pair(app: FfcCalibrationApp, calibration: dai.CalibrationHandler, idx: int) -> StereoPair:
    pairs = app.get_all_stereo_pairs(calibration)
    if not pairs:
        raise RuntimeError("No usable stereo pair could be derived from the calibration.")
    return pairs[idx % len(pairs)]


def _largest_baseline_pair_idx(
    pairs: list[StereoPair],
    calibration: dai.CalibrationHandler,
) -> int:
    best_idx = 0
    best_baseline = -1.0
    for idx, pair in enumerate(pairs):
        tvec = np.asarray(
            calibration.getCameraTranslationVector(pair.left, pair.right, False)
        ).reshape(-1)
        baseline = float(np.linalg.norm(tvec))
        if baseline > best_baseline:
            best_baseline = baseline
            best_idx = idx
    return best_idx


def _disable_pipeline_auto_calibration(pipeline: dai.Pipeline) -> None:
    pipeline.setAutoCalibrationMode(dai.Pipeline.AutoCalibrationMode.OFF)


def _run_dynamic_calibration(
    app: FfcCalibrationApp,
    calibration: dai.CalibrationHandler,
    visualizer: dai.RemoteConnection,
    frontend_state: FfcFrontendState,
    topic_toggles: TopicToggles,
) -> tuple[dai.CalibrationHandler | None, str | None]:
    with app.open_device() as device:
        with dai.Pipeline(device) as pipeline:
            _disable_pipeline_auto_calibration(pipeline)
            preview_outs = {}
            for socket in app.sockets:
                cam = pipeline.create(dai.node.Camera).build(socket)
                out = cam.requestOutput(app.resolution, fps=app.fps)
                preview_outs[socket] = out

            first_pair = _selected_pair(app, calibration, 0)
            stereo = pipeline.create(dai.node.StereoDepth)
            preview_outs[first_pair.left].link(stereo.left)
            preview_outs[first_pair.right].link(stereo.right)
            dyn_calib = pipeline.create(dai.node.DynamicCalibration)
            for socket, out in preview_outs.items():
                out.link(dyn_calib.inputs[f"input_{int(socket)}"])

            dashboard = pipeline.create(CalibrationDashboardNode).build(
                preview=stereo.syncedLeft,
                calibration=calibration,
                sockets=app.sockets,
                pairs=app.get_all_stereo_pairs(calibration),
            )
            left_overlay = pipeline.create(CoverageOverlayNode).build(stereo.syncedLeft)
            right_overlay = pipeline.create(CoverageOverlayNode).build(stereo.syncedRight)
            dashboard.set_state(
                "calibrating",
                title="FFC Calibration",
                status_lines=[
                    "Camera relative pose.",
                    "Coverage is rendered on the left/right capture streams.",
                ],
            )

            calibration_output = dyn_calib.calibrationOutput.createOutputQueue(maxSize=1, blocking=False)
            dashboard_coverage_output = dyn_calib.coverageOutput.createOutputQueue(maxSize=1, blocking=False)
            input_control = dyn_calib.inputControl.createInputQueue()

            _reset_topics(
                visualizer,
                [
                    "Dashboard",
                    "Left",
                    "Right",
                    "Depth",
                ],
            )
            _add_enabled_topics(
                visualizer,
                topic_toggles,
                dashboard_out=dashboard.dashboard,
                left_out=left_overlay.output,
                right_out=right_overlay.output,
                depth_out=stereo.disparity,
            )

            pipeline.start()
            visualizer.registerPipeline(pipeline)
            time.sleep(1.0)

            input_control.send(
                dai.DynamicCalibrationControl.setPerformanceMode(
                    dai.DynamicCalibrationControl.PerformanceMode.OPTIMIZE_PERFORMANCE
                )
            )
            input_control.send(dai.DynamicCalibrationControl.startCalibration(keepCameraCenters=True))

            new_calibration = None
            while pipeline.isRunning():
                visualizer.waitKey(1)
                pipeline.processTasks()

                navigation = frontend_state.consume_navigation_request()
                if navigation is not None:
                    try:
                        input_control.send(dai.DynamicCalibrationControl.stopCalibration())
                    except Exception:
                        pass
                    return None, navigation.stage

                coverage = dashboard_coverage_output.tryGet()
                if coverage is not None:
                    pct = 0.0
                    coverage_map = getattr(coverage, "coveragePerCell", None)
                    left_cells = None
                    right_cells = None
                    if coverage_map is not None:
                        try:
                            left_cells = coverage_map[first_pair.left]
                        except Exception:
                            left_cells = None
                        try:
                            right_cells = coverage_map[first_pair.right]
                        except Exception:
                            right_cells = None

                    sample_cells = left_cells if left_cells is not None else right_cells
                    if sample_cells is not None:
                        arr = np.asarray(sample_cells, dtype=np.float32).ravel()
                        arr = arr[np.isfinite(arr)]
                        if arr.size > 0:
                            mx = float(np.max(arr))
                            pct = float(np.mean(arr) * (100.0 if mx <= 1.01 else 1.0))
                    data_acquired = getattr(coverage, "dataAcquired", None)
                    if data_acquired is not None:
                        value = float(data_acquired)
                        if np.isfinite(value):
                            pct = max(pct, value * 100.0 if 0.0 <= value <= 1.0 else value)
                    left_overlay.set_coverage(left_cells, pct, "Capturing calibration frames")
                    right_overlay.set_coverage(right_cells, pct, "Capturing calibration frames")

                result = calibration_output.tryGet()
                if result is not None:
                    calibration_data = result.calibrationData
                    print(
                        f"[dyn-calib] info={getattr(result, 'info', '')} "
                        f"has_data={calibration_data is not None}",
                        flush=True,
                    )
                    if calibration_data is not None:
                        new_calibration = calibration_data.newCalibration
                        input_control.send(
                            dai.DynamicCalibrationControl.applyCalibration(
                                new_calibration,
                                flash=False,
                            )
                        )
                        dashboard.set_progress(100.0, "Calibration complete")
                        break

            if new_calibration is None:
                raise RuntimeError("DynamicCalibration did not return calibration data")

            entered_baselines = getattr(app, "entered_baselines_cm", {})
            if entered_baselines:
                new_calibration = app.constrain_calibration_to_entered_baselines(
                    new_calibration,
                    entered_baselines,
                )
                app._log_entered_baseline_readback(
                    new_calibration,
                    entered_baselines,
                    header="Re-applied entered baselines after dynamic calibration",
                )

            print("Calibration complete.")
            return new_calibration, None


def _pair_menu(
    app: FfcCalibrationApp,
    calibration: dai.CalibrationHandler,
    visualizer: dai.RemoteConnection,
    frontend_state: FfcFrontendState,
    topic_toggles: TopicToggles,
) -> str | None:
    pairs = app.get_all_stereo_pairs(calibration)
    selected_idx = _largest_baseline_pair_idx(pairs, calibration)
    frontend_state.update_pairs(
        pairs,
        calibration,
        getattr(app, "entered_baselines_cm", {}),
        selected_idx,
    )

    while True:
        selected_pair = pairs[selected_idx]
        with app.open_device() as device:
            with dai.Pipeline(device) as pipeline:
                _disable_pipeline_auto_calibration(pipeline)
                cam_left = pipeline.create(dai.node.Camera).build(selected_pair.left)
                cam_right = pipeline.create(dai.node.Camera).build(selected_pair.right)
                sync = pipeline.create(dai.node.Sync)
                sync.setSyncThreshold(timedelta(milliseconds=50))
                stereo = pipeline.create(dai.node.StereoDepth)
                stereo.setRectification(True)
                depth_preview = pipeline.create(DepthPreviewNode).build(
                    stereo.depth,
                    min_distance_mm=300,
                    max_distance_mm=5000,
                    state=frontend_state._depth_preview,
                )
                shared_resolution = app.preview_resolution_for_pair(
                    selected_pair.left, selected_pair.right
                )
                left_raw = cam_left.requestOutput(shared_resolution, fps=app.fps)
                right_raw = cam_right.requestOutput(shared_resolution, fps=app.fps)
                left_raw.link(sync.inputs["left"])
                right_raw.link(sync.inputs["right"])
                left_raw.link(stereo.left)
                right_raw.link(stereo.right)
                device.setCalibration(calibration)

                left_out = stereo.syncedLeft
                right_out = stereo.syncedRight

                dashboard = pipeline.create(CalibrationDashboardNode).build(
                    preview=left_out,
                    calibration=calibration,
                    sockets=app.sockets,
                    pairs=pairs,
                )
                dashboard.set_state(
                    "preview",
                    title="FFC Calibration",
                    status_lines=[
                        f"Currently displaying: {selected_pair.label()}",
                        "Use the browser controls to select pairs or flash calibration.",
                    ],
                    selected_pair_idx=selected_idx,
                    entered_baselines=getattr(app, "entered_baselines_cm", {}),
                )

                _reset_topics(
                    visualizer,
                    [
                        "Dashboard",
                        "Left",
                        "Right",
                        "Depth",
                    ],
                )
                _add_enabled_topics(
                    visualizer,
                    topic_toggles,
                    dashboard_out=dashboard.dashboard,
                    left_out=left_out,
                    right_out=right_out,
                    depth_out=depth_preview.output,
                )

                left_probe = (
                    left_out.createOutputQueue(maxSize=1, blocking=False)
                    if topic_toggles.left
                    else None
                )
                right_probe = (
                    right_out.createOutputQueue(maxSize=1, blocking=False)
                    if topic_toggles.right
                    else None
                )
                depth_probe = (
                    depth_preview.output.createOutputQueue(maxSize=1, blocking=False)
                    if topic_toggles.depth
                    else None
                )

                pipeline.start()
                visualizer.registerPipeline(pipeline)

                while pipeline.isRunning():
                    visualizer.waitKey(1)
                    pipeline.processTasks()

                    if left_probe is not None:
                        left_probe.tryGet()
                    if right_probe is not None:
                        right_probe.tryGet()
                    if depth_probe is not None:
                        depth_probe.tryGet()

                    if frontend_state.consume_flash_request():
                        try:
                            app.flash_calibration(calibration)
                            frontend_state.set_flash_status("Calibration flashed to device.")
                        except Exception as exc:
                            frontend_state.set_flash_status(f"Flash failed: {exc}")

                    requested_idx = frontend_state.consume_pair_request()
                    if requested_idx is not None and requested_idx < len(pairs):
                        selected_idx = requested_idx
                        frontend_state.update_pairs(
                            pairs,
                            calibration,
                            getattr(app, "entered_baselines_cm", {}),
                            selected_idx,
                        )
                        break

                    navigation = frontend_state.consume_navigation_request()
                    if navigation is not None:
                        return navigation.stage


def main() -> None:
    _, args = initialize_argparser()

    device_id = _choose_device(args.device)
    if device_id is None:
        return

    app = FfcCalibrationApp(device_id, fps=args.fps_limit)
    topic_toggles = TopicToggles(
        dashboard=not args.disable_dashboard,
        left=not args.disable_left,
        right=not args.disable_right,
        depth=not args.disable_depth,
    )
    visualizer, ws_port = _make_visualizer(args.http_port, args.ws_port)
    frontend_state = FfcFrontendState(app, topic_toggles)
    visualizer.registerService(STATE_SERVICE, frontend_state.handle_get_state)
    visualizer.registerService(SOCKET_SERVICE, frontend_state.handle_set_sockets)
    visualizer.registerService(BASELINE_SERVICE, frontend_state.handle_set_baselines)
    visualizer.registerService(PAIR_SERVICE, frontend_state.handle_select_pair)
    visualizer.registerService(FLASH_SERVICE, frontend_state.handle_flash_request)
    visualizer.registerService(NAVIGATE_SERVICE, frontend_state.handle_navigate)
    visualizer.registerService(DEPTH_CURSOR_SERVICE, frontend_state.handle_set_depth_cursor)
    visualizer.registerService(DEPTH_RANGE_SERVICE, frontend_state.handle_set_depth_range)
    visualizer.registerService(DEPTH_STATE_SERVICE, frontend_state.handle_get_depth_state)
    print(f"Connected to device: {app.deviceId}")

    print(
        "Open the FFC frontend and select sockets/baselines. "
        f"WebSocket URL: ws://localhost:{ws_port}"
    )
    print(
        "Enabled topics: "
        f"dashboard={topic_toggles.dashboard} "
        f"left={topic_toggles.left} "
        f"right={topic_toggles.right} "
        f"depth={topic_toggles.depth}"
    )
    while True:
        try:
            frontend_state.wait_for_socket_selection()
            entered_baselines = frontend_state.wait_for_baselines()
        except RuntimeError as exc:
            if str(exc).startswith("NAVIGATE:"):
                continue
            raise

        app.entered_baselines_cm = entered_baselines
        try:
            calibration = app.create_eeprom(use_device_calibration=True)
        except ValueError as exc:
            frontend_state.reject_baselines(str(exc))
            continue
        calibration, navigation_stage = _run_dynamic_calibration(
            app, calibration, visualizer, frontend_state, topic_toggles
        )
        if navigation_stage is not None:
            continue
        if calibration is None:
            continue

        frontend_state.set_stage("preview", "Dynamic calibration complete.")
        navigation_stage = _pair_menu(
            app, calibration, visualizer, frontend_state, topic_toggles
        )
        if navigation_stage is not None:
            continue


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
