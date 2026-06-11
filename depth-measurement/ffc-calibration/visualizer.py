from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass

import numpy as np

from utils.depthai_path import configure_depthai_path

configure_depthai_path()

import depthai as dai

from utils.arguments import initialize_argparser
from utils.ffc_calibration import (
    CalibrationDashboardNode,
    FfcCalibrationApp,
    StereoPair,
    format_socket,
)

BASELINE_SERVICE = "FFC Set Baselines"
SOCKET_SERVICE = "FFC Set Sockets"
FLASH_SERVICE = "FFC Flash Calibration"
STATE_SERVICE = "FFC State"
PAIR_SERVICE = "FFC Select Pair"


@dataclass
class FfcPairStats:
    label: str
    left: str
    right: str
    baseline_cm: float
    translation: list[float]
    entered_baseline_cm: float | None = None


class FfcFrontendState:
    def __init__(self, app: FfcCalibrationApp):
        self._app = app
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

    def wait_for_baselines(self) -> dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float]:
        while True:
            with self._lock:
                if self._baseline_ready:
                    return {
                        self._socket_key_to_pair(key): value
                        for key, value in self._baselines.items()
                    }
            time.sleep(0.05)

    def wait_for_socket_selection(self) -> None:
        while True:
            with self._lock:
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
            if value <= 0:
                return {"ok": False, "error": f"Baseline must be positive for {field['left']} -> {field['right']}"}
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

    def handle_flash_request(self, _req=None) -> dict:
        with self._lock:
            self._flash_requested = True
            self._flash_status = "Flash requested."
        return {"ok": True}

    def consume_flash_request(self) -> bool:
        with self._lock:
            requested = self._flash_requested
            self._flash_requested = False
            return requested

    def set_flash_status(self, status: str) -> None:
        with self._lock:
            self._flash_status = status

    def handle_get_state(self, _req=None) -> dict:
        with self._lock:
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
) -> dai.CalibrationHandler:
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
            dashboard.set_state(
                "calibrating",
                title="FFC Calibration",
                status_lines=[
                    "Camera relative pose and capture progress.",
                ],
            )

            calibration_output = dyn_calib.calibrationOutput.createOutputQueue(maxSize=1, blocking=False)
            dashboard_coverage_output = dyn_calib.coverageOutput.createOutputQueue(maxSize=1, blocking=False)
            input_control = dyn_calib.inputControl.createInputQueue()

            visualizer.addTopic("Dashboard", dashboard.dashboard, "dashboard")
            visualizer.addTopic("Left", stereo.syncedLeft, "images")
            visualizer.addTopic("Right", stereo.syncedRight, "images")
            visualizer.addTopic("Depth", stereo.depth, "depth")

            pipeline.start()
            visualizer.registerPipeline(pipeline)

            input_control.send(
                dai.DynamicCalibrationControl.setPerformanceMode(
                    dai.DynamicCalibrationControl.PerformanceMode.SKIP_CHECKS
                )
            )
            input_control.send(
                dai.DynamicCalibrationControl.startCalibration(
                    loadImagePeriod=0.5,
                    calibrationPeriod=5.0,
                )
            )

            new_calibration = None
            while pipeline.isRunning():
                visualizer.waitKey(1)
                pipeline.processTasks()

                coverage = dashboard_coverage_output.tryGet()
                if coverage is not None:
                    pct = 0.0
                    cvec = getattr(coverage, "coveragePerCellA", None)
                    if cvec is not None:
                        arr = np.asarray(cvec, dtype=np.float32).ravel()
                        arr = arr[np.isfinite(arr)]
                        if arr.size > 0:
                            mx = float(np.max(arr))
                            pct = float(np.mean(arr) * (100.0 if mx <= 1.01 else 1.0))
                    data_acquired = getattr(coverage, "dataAcquired", None)
                    if data_acquired is not None:
                        value = float(data_acquired)
                        if np.isfinite(value):
                            pct = max(pct, value * 100.0 if 0.0 <= value <= 1.0 else value)
                    dashboard.set_progress(pct, "Capturing calibration frames")

                result = calibration_output.tryGet()
                if result is not None and result.calibrationData:
                    new_calibration = result.calibrationData.newCalibration
                    input_control.send(dai.DynamicCalibrationControl.stopCalibration())
                    input_control.send(
                        dai.DynamicCalibrationControl(
                            dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                                new_calibration
                            )
                        )
                    )
                    dashboard.set_progress(100.0, "Calibration complete")
                    break

            if new_calibration is None:
                raise RuntimeError("DynamicCalibration did not return calibration data")

            print("Calibration complete.")
            return new_calibration


def _pair_menu(
    app: FfcCalibrationApp,
    calibration: dai.CalibrationHandler,
    visualizer: dai.RemoteConnection,
    frontend_state: FfcFrontendState,
):
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
                stereo = pipeline.create(dai.node.StereoDepth)
                stereo.setRectification(True)
                cam_left.requestOutput(app.resolution, fps=app.fps).link(stereo.left)
                cam_right.requestOutput(app.resolution, fps=app.fps).link(stereo.right)

                left_out = stereo.rectifiedLeft
                right_out = stereo.rectifiedRight
                depth_out = stereo.depth

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
                visualizer.addTopic("Dashboard", dashboard.dashboard, "dashboard")
                visualizer.addTopic("Left", left_out, "images")
                visualizer.addTopic("Right", right_out, "images")
                visualizer.addTopic("Depth", depth_out, "depth")

                pipeline.start()
                visualizer.registerPipeline(pipeline)

                while pipeline.isRunning():
                    visualizer.waitKey(1)
                    pipeline.processTasks()

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


def main() -> None:
    _, args = initialize_argparser()

    device_id = _choose_device(args.device)
    if device_id is None:
        return

    app = FfcCalibrationApp(device_id, fps=args.fps_limit)
    visualizer, ws_port = _make_visualizer(args.http_port, args.ws_port)
    frontend_state = FfcFrontendState(app)
    visualizer.registerService(STATE_SERVICE, frontend_state.handle_get_state)
    visualizer.registerService(SOCKET_SERVICE, frontend_state.handle_set_sockets)
    visualizer.registerService(BASELINE_SERVICE, frontend_state.handle_set_baselines)
    visualizer.registerService(PAIR_SERVICE, frontend_state.handle_select_pair)
    visualizer.registerService(FLASH_SERVICE, frontend_state.handle_flash_request)
    print(f"Connected to device: {app.deviceId}")

    print(
        "Open the FFC frontend and select sockets/baselines. "
        f"WebSocket URL: ws://localhost:{ws_port}"
    )
    frontend_state.wait_for_socket_selection()
    entered_baselines = frontend_state.wait_for_baselines()
    app.entered_baselines_cm = entered_baselines
    calibration = app.create_eeprom(use_device_calibration=True)
    calibration = _run_dynamic_calibration(app, calibration, visualizer, frontend_state)
    frontend_state.set_stage("preview", "Dynamic calibration complete.")
    _pair_menu(app, calibration, visualizer, frontend_state)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
