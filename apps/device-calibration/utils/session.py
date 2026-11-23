"""The calibration flow: phases, board setup, processing, IMU mounting and the single Flash.

The frontend polls `state()` and sends `action()`; nodes never call back into `Session`.
Lock order is Session -> node. The processing thread takes the Session lock only to publish.
"""

import base64
import copy
import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

import depthai as dai
import numpy as np

from utils.board_config import (
    Boards,
    ImuMounting,
    _mounting_from_board,
    _mounting_from_eeprom,
    board_from_device,
    prepare,
    problems,
)
from utils.camera_calibration import CalibrationError, Rig, calibrate_rig, transform
from utils.charuco import DICTIONARIES, BoardSpec, load_dataset, make_board, render_png
from utils.device_info import read_device_info
from utils.eeprom import apply_rig, rig_from_handler
from utils.imu_calibration import (
    ImuCalibration,
    Mounting,
    refine_rotation,
    spec_error,
    with_rotation,
)
from utils.validation import board_pose, report

FROM_DEVICE = "From device"
MIN_FREE_BYTES = 1_000_000_000  # 25 sets of 12 MP + 2 x 1 MP PNGs are about 250 MB
MAX_BOARD_DRIFT_DEG = 5.0  # board-refined IMU rotation vs the six-pose mapping
RESULT_KEYS = ("cameras", "pairs", "stereo", "problems", "warnings")

SETUP, CAPTURE, PROCESSING, RESULTS, IMU, REVIEW = "setup", "capture", "processing", "results", "imu", "review"
# action -> the only phases it is accepted in
ACTIONS: Dict[str, Tuple[str, ...]] = {
    "select_board": (SETUP,), "set_board": (SETUP,), "start_capture": (SETUP,), "skip_cameras": (SETUP,),
    "capture": (CAPTURE,), "set_auto": (CAPTURE,), "set_view": (CAPTURE,), "undo_set": (CAPTURE,),
    "back": (CAPTURE,), "process": (CAPTURE,),
    "cancel": (PROCESSING,),
    "recapture": (RESULTS,), "discard": (RESULTS,), "accept": (RESULTS, IMU),
    "imu_capture": (IMU,), "imu_back": (IMU,), "imu_redo": (IMU,), "skip_imu": (IMU,),
    "flash": (REVIEW,), "restart": (REVIEW,),
}


class _Cancelled(Exception):
    pass


class _ImuFit(NamedTuple):
    result: ImuCalibration  # with the final IMU -> camera rotation
    mounting: dict  # ImuMounting JSON
    problems: List[str]


def _spec(charuco: dict) -> BoardSpec:
    try:
        spec = BoardSpec(
            int(charuco["squaresX"]), int(charuco["squaresY"]), float(charuco["squareCm"]),
            float(charuco["markerCm"]), str(charuco["dictionary"]),
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("Fill in all ChArUco fields.") from None
    if problem := spec.problem():
        raise ValueError(problem)
    return spec


def _charuco(spec: BoardSpec) -> dict:
    return {"squaresX": spec.squares_x, "squaresY": spec.squares_y, "squareCm": spec.square_cm,
            "markerCm": spec.marker_cm, "dictionary": spec.dictionary}


def _imu_json(result: ImuCalibration, spec: Optional[np.ndarray], flashed: bool) -> dict:
    return {
        "rotation": result.rotation.tolist(),
        "accelerometer": result.accelerometer.tolist(),
        "gyroscope": result.gyroscope.tolist(),
        "poseTilts": result.pose_tilts.tolist(),
        "fitError": result.fit_error,
        "problems": result.problems,
        "specMatch": None if spec is None else bool(np.allclose(result.rotation, spec)),
        "flashed": flashed,
    }


class Session:
    def __init__(self, device: dai.Device, boards: Boards, capture, imu, live_gates: Dict[str, dai.InputQueue], args) -> None:
        self._device, self._boards, self._capture, self._imu = device, boards, capture, imu
        self._gates, self._args = live_gates, args
        self._lock = threading.Lock()
        self._id = int(time.time())  # lets the frontend tell a backend restart from a stale reply
        self._features = device.getConnectedCameraFeatures()
        self._out: Path = args.output_dir
        # Board names are depthai-boards file names without ".json"; --board-config adds one more.
        self._files = {}
        if args.board_config:
            self._files[args.board_config.stem] = json.loads(args.board_config.read_text())["board_config"]
        self._names = [*self._files, *(n.removesuffix(".json") for n in boards.names), FROM_DEVICE]
        calibration = device.readCalibration2()
        detected = args.board_config.stem if args.board_config else (boards.detect(
            calibration.getEepromData(), device.getDeviceName()) or "").removesuffix(".json")
        self.mounting = self._resolve_mounting(calibration, detected)
        self._device_info = read_device_info(device, self.mounting)
        self._last_charuco = self._read_last_charuco()
        self._board: dict = {"name": "", "cameras": {}}
        self._source, self._board_info = "none", ("", "")
        if detected:
            self._select(detected, f"detected: {detected}.json")
        self._cancel = threading.Event()
        self._message, self._message_ok = "", False
        self._reset()

    def _resolve_mounting(self, calibration: dai.CalibrationHandler, name: Optional[str]) -> ImuMounting:
        try:
            return _mounting_from_board(self._get(name), self._device.getConnectedIMU(), f"{name}.json")
        except (KeyError, LookupError):
            return _mounting_from_eeprom(calibration.getEepromData(), "EEPROM (no usable depthai-boards entry)")

    def _get(self, name: str) -> dict:
        return self._files[name] if name in self._files else self._boards.get(f"{name}.json")

    def _read_last_charuco(self) -> Optional[dict]:
        try:
            return _charuco(_spec(json.loads((self._out / "charuco.json").read_text())))
        except (OSError, ValueError):
            return None

    def _reset(self) -> None:
        """Back to a clean setup; the board config and the on-disk datasets stay."""
        self._phase = SETUP
        self._spec: Optional[BoardSpec] = None
        self._board_fixed = False
        self._dir: Optional[Path] = None
        self._progress: Tuple[float, str] = (0.0, "")
        self._rig: Optional[Rig] = None
        self._obs: dict = {}
        self._result: Optional[dict] = None
        self._fit: Optional[_ImuFit] = None
        self._flashed, self._backup = False, None

    # ---- services ----

    def board_preview(self, request: dict) -> dict:
        try:
            spec = _spec(request)
        except ValueError as e:
            return {"error": str(e)}
        return {
            "png": base64.b64encode(render_png(spec)).decode(),
            "widthCm": spec.squares_x * spec.square_cm,
            "heightCm": spec.squares_y * spec.square_cm,
        }

    def state(self, since: int) -> dict:
        with self._lock:
            capture = dict(self._capture.state()) if self._phase == CAPTURE else None
            message = (capture or {}).pop("message", "") or self._message
            imu = self._imu_state(since)
            return {
                "session": self._id,
                "phase": self._phase,
                "message": message,
                "messageOk": bool(message) and self._message_ok,
                "device": self._device_info,
                "boardNames": self._names,
                "boardSource": self._source,
                "board": self._board,
                "boardProblems": problems(self._board) if self._board["cameras"] else [],
                "dictionaries": DICTIONARIES,
                "lastCharuco": self._last_charuco,
                "charuco": self._spec and _charuco(self._spec),
                "boardFixed": self._board_fixed,
                "capture": capture or None,
                "processing": {"progress": self._progress[0], "stage": self._progress[1]}
                if self._phase == PROCESSING else None,
                "cameraResult": self._result and {k: self._result[k] for k in RESULT_KEYS},
                "imu": imu,
                "imuMounting": self._fit and self._fit.mounting,
                "problems": self._blockers(),
                "dryRun": self._args.dry_run,
                "flashed": self._flashed,
                "backupPath": self._backup,
            }

    def action(self, request: dict) -> dict:
        name = str(request.get("action"))
        with self._lock:
            if self._phase not in ACTIONS.get(name, ()):
                return {"ok": False, "error": f"'{name}' is not available in the {self._phase} step."}
            self._message, self._message_ok = "", False
            error = getattr(self, f"_do_{name}")(request)
            if error:
                self._message = error
            return {"ok": False, "error": error} if error else {"ok": True}

    # ---- setup ----

    def _select(self, name: str, source: str) -> None:
        if name == FROM_DEVICE:
            board = board_from_device(self._features, self._device.readCalibration2())
        else:
            board = self._get(name)
        self._board, self._source = prepare(board, self._features), source
        # What an empty EEPROM gets as board info; the frontend's board name is the config name.
        self._board_info = (self._board["name"], self._board.get("revision") or "")
        self._board["name"] = name

    def _do_select_board(self, request: dict) -> Optional[str]:
        name = request.get("name")
        if name not in self._names:
            return f"Unknown board config {name}."
        self._select(name, "from device" if name == FROM_DEVICE else "selected")

    def _do_set_board(self, request: dict) -> Optional[str]:
        board = request.get("board")
        if not isinstance(board, dict) or set(board.get("cameras", ())) != set(self._board["cameras"]):
            return "The edited board does not match the current one."
        self._board = board

    def _do_start_capture(self, request: dict) -> Optional[str]:
        try:
            spec = _spec(request.get("charuco") or {})
        except ValueError as e:
            return str(e)
        if problems(self._board) or not self._board["cameras"]:
            return "Fix the board config first."
        self._out.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self._out).free < MIN_FREE_BYTES:
            return f"Less than 1 GB free in {self._out}."
        self._reset()
        self._spec, self._board_fixed = spec, bool(request.get("boardFixed"))
        self._dir = self._out / f"dataset_{datetime.now():%Y%m%d_%H%M%S}"
        self._capture.start(copy.deepcopy(self._board), spec, self._board_fixed, self._dir,
                            self._imu.recent_accel_mean if self._imu else lambda: None)
        self._last_charuco = _charuco(spec)
        (self._out / "charuco.json").write_text(json.dumps(self._last_charuco))
        self._enter_capture()

    def _do_skip_cameras(self, request: dict) -> Optional[str]:
        if not self._imu:
            return "This device has no IMU."
        self._phase = IMU

    # ---- capture ----

    def _gates_open(self, open_: bool) -> None:
        # The factories return a new control; a default GateControl() is open.
        control = dai.GateControl.openGate() if open_ else dai.GateControl.closeGate()
        for queue in self._gates.values():
            queue.send(control)

    def _enter_capture(self) -> None:
        self._phase = CAPTURE
        self._gates_open(True)

    def _do_capture(self, request: dict) -> Optional[str]:
        if not self._capture.action("capture"):
            return "No camera sees the board, or a capture is already running."

    def _do_undo_set(self, request: dict) -> Optional[str]:
        if not self._capture.action("undo_set"):
            return "Nothing to undo."

    def _do_set_auto(self, request: dict) -> Optional[str]:
        self._capture.action("set_auto", request.get("value"))

    def _do_set_view(self, request: dict) -> Optional[str]:
        if not self._capture.action("set_view", request.get("pair")):
            return "Unknown camera pair."

    def _leave_capture(self, drop_dataset: bool = False) -> None:
        self._capture.stop()
        self._gates_open(False)
        if drop_dataset and self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
        self._reset()

    def _do_back(self, request: dict) -> Optional[str]:
        self._leave_capture(drop_dataset=True)

    def _do_process(self, request: dict) -> Optional[str]:
        if not self._capture.state()["canProcess"]:
            return "Every camera pair needs at least 5 shared views."
        self._gates_open(False)
        self._cancel.clear()
        self._progress = (0.0, "Starting")
        self._phase = PROCESSING
        threading.Thread(target=self._process, args=(self._dir, self._board, self._spec), daemon=True).start()

    # ---- processing (own thread) ----

    def _process(self, directory: Path, board: dict, spec: BoardSpec) -> None:
        def progress(start: float, span: float) -> Callable[[float, str], None]:
            def publish(fraction: float, stage: str) -> None:
                if self._cancel.is_set():
                    raise _Cancelled
                with self._lock:
                    self._progress = (start + span * fraction, stage)
            return publish

        try:
            names = {s: c["name"] for s, c in board["cameras"].items() if c["enabled"]}
            obs = load_dataset(directory, names, spec, progress(0.0, 0.6))
            rig = calibrate_rig(board, obs, spec, progress(0.6, 0.3))
            progress(0.9, 0.0)(0.0, "Validating")
            old = rig_from_handler(self._device.readCalibration2(), board, {s: c.size for s, c in rig.cameras.items()})
            result = report(rig, old, board, obs, spec)
            (self._out / f"report_{datetime.now():%Y%m%d_%H%M%S}.json").write_text(json.dumps(result))
        except _Cancelled:
            return self._processing_failed("")
        except CalibrationError as e:
            return self._processing_failed(str(e))
        except Exception as e:  # a thread must not die silently with the UI stuck on "processing"
            return self._processing_failed(f"Processing failed: {e}")
        with self._lock:
            if self._cancel.is_set():  # Cancel arrived after the last progress check
                self._message, self._message_ok = "", False
                return self._enter_capture()
            self._rig, self._obs, self._result, self._phase = rig, obs, result, RESULTS

    def _processing_failed(self, message: str) -> None:
        with self._lock:
            self._message, self._message_ok = message, False
            self._enter_capture()

    def _do_cancel(self, request: dict) -> Optional[str]:
        self._cancel.set()

    # ---- results ----

    def _do_recapture(self, request: dict) -> Optional[str]:
        self._rig = self._result = None
        self._enter_capture()

    def _do_discard(self, request: dict) -> Optional[str]:
        self._leave_capture(drop_dataset=True)

    def _do_accept(self, request: dict) -> Optional[str]:
        if self._phase == RESULTS:
            if self._result["problems"]:
                return "Fix the camera problems first."
            self._capture.stop()
            self._phase = IMU if self._imu else REVIEW
        elif self._current_fit() is None:
            return "Finish the six poses first."
        else:
            self._phase = REVIEW

    # ---- IMU ----

    def _imu_state(self, since: int) -> Optional[dict]:
        if self._imu is None:
            return None
        state, fit = self._imu.state(since), self._current_fit()
        state["result"] = fit and _imu_json(fit.result, self.mounting.spec_rotation, self._flashed)
        return state

    def _current_fit(self) -> Optional[_ImuFit]:
        six = self._imu and self._imu.result
        if six is not None and self._fit is None:
            self._fit = self._fit_imu(six)
        return self._fit

    def _fit_imu(self, six: ImuCalibration) -> _ImuFit:
        try:
            mounting = self._refine(six)
        except (OSError, ValueError, KeyError, np.linalg.LinAlgError) as e:  # a bad dataset must not break every poll
            mounting = Mounting(six.rotation, "six-pose", f"Board refinement failed: {e}", 0, None, None)
        spec = self.mounting.spec_rotation
        rpy, total = spec_error(mounting.rotation, spec) if spec is not None else (None, None)
        found = []
        if mounting.source == "board":
            drift = spec_error(mounting.rotation, six.rotation)[1]
            if drift > MAX_BOARD_DRIFT_DEG:
                found.append(f"Board-refined IMU rotation is {drift:.1f} deg from the six-pose mapping; recapture.")
        return _ImuFit(
            with_rotation(six, mounting.rotation),
            {"source": mounting.source, "reason": mounting.reason, "sets": mounting.sets,
             "spreadDeg": mounting.spread_deg, "residualDeg": mounting.residual_deg,
             "specErrorRpyDeg": rpy, "specErrorDeg": total},
            found,
        )

    def _refine(self, six: ImuCalibration) -> Mounting:
        """IMU -> to_cam rotation from the board views, or the six-pose mapping with the reason why not."""
        def keep(reason: str) -> Mounting:
            return Mounting(six.rotation, "six-pose", reason, 0, None, None)

        if self._rig is None:
            return keep("Cameras were skipped, so there are no board views.")
        if not self._board_fixed:
            return keep("The board was moved, so gravity in the board frame is not constant.")
        to_cam, board = self.mounting.socket.name, make_board(self._spec)
        accel, poses = [], []
        for record in json.loads((self._dir / "sets.json").read_text())["sets"]:
            if record["accel"] is None:
                continue
            for cam in dict.fromkeys([to_cam, *record["cameras"]]):  # to_cam first, else any camera linked to it
                det = self._obs.get(cam, {}).get(record["key"])
                T = transform(self._rig, cam, to_cam) if det else None
                if T is not None:
                    poses.append((T @ board_pose(self._rig.cameras[cam], det, board))[:3, :3])
                    accel.append(six.scale * (np.asarray(record["accel"]) - six.offset))
                    break
        return refine_rotation(np.reshape(accel, (-1, 3)), np.reshape(poses, (-1, 3, 3)), six.rotation)

    def _do_imu_capture(self, request: dict) -> Optional[str]:
        if not self._imu.action("capture")["ok"]:
            return "The IMU is not ready or a capture is running."

    def _do_imu_back(self, request: dict) -> Optional[str]:
        self._imu.action("back")

    def _do_imu_redo(self, request: dict) -> Optional[str]:
        self._imu.action("redo")
        self._fit = None

    def _do_skip_imu(self, request: dict) -> Optional[str]:
        self._do_imu_redo(request)  # also stops a capture under way, so no IMU part sneaks into the flash
        self._phase = REVIEW

    # ---- review and flash ----

    def _blockers(self) -> List[str]:
        imu = self._imu and self._imu.result
        return [
            *(self._result["problems"] if self._result else []),
            *(imu.problems if imu else []),
            *(self._fit.problems if self._fit else []),
        ]

    def _do_flash(self, request: dict) -> Optional[str]:
        if self._flashed:
            return "Already done. Press Start over first."
        if self._blockers():
            return "Fix the problems before flashing."
        if self._rig is None and self._fit is None:
            return "There is nothing to write."
        try:
            self._flash()
        except RuntimeError as e:
            return f"Flash failed: {e}"
        self._flashed, self._message_ok = True, True
        self._device_info = read_device_info(self._device, self.mounting)

    def _flash(self) -> None:
        stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
        calibration = self._device.readCalibration2()
        self._out.mkdir(parents=True, exist_ok=True)
        backup = (self._out / f"calibration_backup_{stamp}.json").resolve()
        calibration.eepromToJsonFile(str(backup))
        self._backup = str(backup)
        data = calibration.getEepromData()
        if not (data.boardName or data.boardRev) and any(self._board_info):  # empty EEPROM, as calibrate.py
            calibration.setBoardInfo(*self._board_info)
        if self._rig:
            apply_rig(calibration, self._rig, self._board)
            data = calibration.getEepromData()
            data.stereoUseSpecTranslation, data.stereoEnableDistortionCorrection = False, True
            calibration = dai.CalibrationHandler(data)
        if self._fit:
            imu = self._fit.result
            calibration.setAccelerometerCalibration(imu.accelerometer.tolist())
            calibration.setGyroscopeCalibration(imu.gyroscope.tolist())
            calibration.setImuExtrinsics(self.mounting.socket, imu.rotation.tolist(),
                                         self.mounting.translation_cm, self.mounting.spec_translation_cm)
        new = (self._out / f"calibration_new_{stamp}.json").resolve()
        calibration.eepromToJsonFile(str(new))
        if self._args.dry_run:
            self._message = f"Dry run: nothing written to the device. Backup: {backup}, new: {new}"
            return
        self._device.flashCalibration(calibration)
        self._message = f"Flashed. Previous calibration saved to {backup}"
        print(self._message)

    def _do_restart(self, request: dict) -> Optional[str]:
        self._leave_capture()
        if self._imu:
            self._imu.action("redo")


if __name__ == "__main__":
    # Self-check with a fake device: python3 -m utils.session
    import tempfile
    from types import SimpleNamespace

    class FakeDevice:
        def __init__(self) -> None:
            self.calibration, self.flashed, self.backups = dai.CalibrationHandler(), [], []

        def readCalibration2(self): return self.calibration
        def getConnectedCameraFeatures(self): return []
        def getDeviceName(self): return "T"
        def getConnectedIMU(self): return "accel"
        def getDeviceId(self): return "fake"
        def getPlatformAsString(self): return "RVC4"
        def getIMUFirmwareVersion(self): return "0"

        def flashCalibration(self, calibration) -> None:
            self.backups.append(sorted(p.name for p in tmp.glob("calibration_backup_*.json")))  # written before the flash
            self.flashed.append(calibration)

    class FakeCapture:
        def start(self, *a): pass
        def stop(self): pass
        def state(self): return {"canProcess": True, "message": ""}
        def action(self, name, value=None): return True

    class FakeImu:
        def __init__(self, result) -> None: self.result = result
        def state(self, since): return {"phase": "results"}
        def action(self, name): return {"ok": True}
        def recent_accel_mean(self): return None

    tmp = Path(tempfile.mkdtemp())
    spin = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])  # 90 deg about z
    board = {"board_config": {"name": "T", "revision": "R1", "cameras": {"CAM_A": {"name": "rgb", "type": "color", "hfov": 70}},
                              "imuExtrinsics": {"sensors": {"imu": {"name": "accel", "extrinsics": {
                                  "to_cam": "CAM_A", "specTranslation": {"x": 0, "y": 0, "z": 0}, "rotationMatrix": spin.tolist()}}}}}}
    six = ImuCalibration(spin, np.hstack([np.eye(3), np.zeros((3, 1))]), np.hstack([np.eye(3), np.zeros((3, 1))]),
                         np.zeros(6), 0.0, [], np.ones(3), np.zeros(3), np.zeros(3))

    def session(dry_run: bool, imu_result=six, rotation=None):
        args = SimpleNamespace(output_dir=tmp, board_config=None, dry_run=dry_run)
        s = Session(FakeDevice(), Boards({"boards/T.json": board}), FakeCapture(), FakeImu(imu_result), {}, args)
        assert s._source == "detected: T.json" and s.mounting.source == "depthai-boards T.json"
        return s

    # every action is rejected outside its phase
    s = session(True)
    for phase in (SETUP, CAPTURE, PROCESSING, RESULTS, IMU, REVIEW):
        s._phase = phase
        for name, allowed in ACTIONS.items():
            if phase not in allowed:
                assert s.action({"action": name})["ok"] is False, (phase, name)
    assert s.action({"action": "nope"})["ok"] is False

    def review(s, problems=()):
        cameras = {"cameras": [], "pairs": [], "stereo": None, "problems": list(problems), "warnings": ["worse"]}
        s.__dict__.update(_phase=REVIEW, _rig=Rig({}, {}), _result=cameras)

    # problems block flash, warnings do not
    s = session(False)
    review(s, ["camera"])
    assert s.action({"action": "flash"})["ok"] is False and not s._device.flashed
    review(s)
    assert s.action({"action": "flash"})["ok"] is True and len(s._device.flashed) == 1
    assert s.action({"action": "flash"})["ok"] is False and len(s._device.flashed) == 1  # no second backup
    assert s._device.backups[0] and s.state(0)["flashed"]  # backup existed when flashCalibration ran
    # --dry-run writes both files and never flashes
    s = session(True)
    review(s)
    assert s.action({"action": "flash"})["ok"] is True and not s._device.flashed
    assert s.state(0)["message"].startswith("Dry run: nothing written to the device.")
    assert Path(s.state(0)["backupPath"]).exists() and list(tmp.glob("calibration_new_*.json"))

    # IMU: a board-refined rotation 7 deg from the six-pose mapping is a problem, a spec mismatch is not
    drift = np.array([[np.cos(np.radians(7)), -np.sin(np.radians(7)), 0], [np.sin(np.radians(7)), np.cos(np.radians(7)), 0], [0, 0, 1]])
    s = session(False)
    s.__dict__.update(_phase=IMU, _rig=Rig({}, {}), _board_fixed=True, _spec=BoardSpec(12, 9, 6.0, 4.7), _dir=tmp)
    (tmp / "sets.json").write_text('{"sets": []}')
    refine_rotation = lambda a, b, init: Mounting(drift @ init, "board", "x", 8, 40.0, 0.2)
    state = s.state(0)
    assert any("7.0 deg from the six-pose mapping" in p for p in state["problems"]), state["problems"]
    assert state["imuMounting"]["source"] == "board" and state["imu"]["result"]["problems"] == []
    s._phase = REVIEW
    assert s.action({"action": "flash"})["ok"] is False and not s._device.flashed
    s = session(False)  # board not declared fixed: six-pose, differs 90 deg from a spec rotated by 90 deg -> no problem
    s._phase, s._rig = IMU, Rig({}, {})
    s.mounting = ImuMounting(dai.CameraBoardSocket.CAM_A, [0.0] * 3, [0.0] * 3, np.eye(3), "t")
    state = s.state(0)
    assert state["problems"] == [] and state["imuMounting"]["specErrorDeg"] > 5
    assert state["imuMounting"]["reason"].startswith("The board was moved")
    print("session self-check passed")
