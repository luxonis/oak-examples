"""IMU mounting (camera socket, translation, spec rotation) from luxonis/depthai-boards."""

import copy
import io
import json
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence

import depthai as dai
import numpy as np

BOARDS_ARCHIVE_URL = "https://codeload.github.com/luxonis/depthai-boards/tar.gz/main"
_BATCH = re.compile(r"batch/[^/]+\.json")
_WANTED = re.compile(r"boards/[^/]+\.json|batch/[^/]+\.json|batch/eeprom/[^/]+\.json")
DEFAULT_HFOV = 70.0  # a few FFC boards list no hfov; the user edits it in the setup table
DEFAULT_LENS_POSITION = 135  # calibrate.py


@dataclass(frozen=True)
class ImuMounting:
    socket: dai.CameraBoardSocket
    translation_cm: List[float]
    spec_translation_cm: List[float]
    spec_rotation: Optional[np.ndarray]  # None when depthai-boards was not available
    source: str


def resolve_mounting(
    calibration: dai.CalibrationHandler, imu_name: str, board_config: Optional[Path]
) -> ImuMounting:
    """Use the depthai-boards spec; fall back to the values already in EEPROM when it cannot be fetched."""
    eeprom = calibration.getEepromData()
    if board_config is not None:
        return _mounting_from_board(
            json.loads(board_config.read_text())["board_config"],
            imu_name,
            board_config.name,
        )
    try:
        boards = Boards(_read_archive(_fetch_archive()))
        name = boards.detect(eeprom, "")
        if name is None:
            raise LookupError(f"no entry for {eeprom.productName} ({eeprom.boardName})")
        return _mounting_from_board(boards.get(name), imu_name, name)
    except (OSError, tarfile.TarError, LookupError, ValueError) as e:
        return _mounting_from_eeprom(
            eeprom, f"EEPROM (depthai-boards lookup failed: {e})"
        )


def _fetch_archive() -> bytes:
    with urllib.request.urlopen(BOARDS_ARCHIVE_URL, timeout=10) as response:
        return response.read()


def _read_archive(data: bytes) -> Dict[str, dict]:
    """Parsed boards/*.json, batch/*.json and batch/eeprom/*.json, keyed by repo-relative path."""
    archive = tarfile.open(fileobj=io.BytesIO(data))
    files = {}
    for m in archive.getmembers():
        path = m.name.split("/", 1)[-1]  # drop the "<repo>-<ref>/" prefix
        if m.isfile() and _WANTED.fullmatch(path):
            files[path] = json.load(archive.extractfile(m))
    return files


def _read_dir(root: Path) -> Dict[str, dict]:
    return {
        p.relative_to(root).as_posix(): json.loads(p.read_text())
        for p in root.glob("**/*.json")
        if _WANTED.fullmatch(p.relative_to(root).as_posix())
    }


class Boards:
    """depthai-boards board configs, keyed by file name (e.g. "OAK-D-PRO.json")."""

    def __init__(self, files: Dict[str, dict]):
        self._files = files
        self.names = sorted(p[len("boards/") :] for p in files if p.startswith("boards/"))

    def get(self, name: str) -> dict:
        return self._files[f"boards/{name}"]["board_config"]

    def detect(self, eeprom: dai.EepromData, device_name: str) -> Optional[str]:
        """Board file for this device: batch EEPROM match, else the normalized product name."""
        for path, batch in self._files.items():
            if not _BATCH.fullmatch(path):
                continue
            for variant in batch.get("variants", []):
                entry = self._files.get(f"batch/{variant.get('eeprom')}")
                config = variant.get("board_config_file")
                if config in self.names and entry and (
                    entry.get("productName"),
                    entry.get("boardName"),
                ) == (eeprom.productName, eeprom.boardName):
                    return config
        for raw in (device_name, eeprom.productName):
            tokens = raw.replace(" ", "-").upper().split("-")
            name = "-".join(t for t in tokens if t not in ("AF", "FF", "9782")) + ".json"
            if name in self.names:
                return name
        return None


def load_boards(boards_dir: Optional[Path], cache_dir: Path) -> Boards:
    """A local directory, else the GitHub archive (cached), else the cache, else no boards."""
    if boards_dir is not None:
        return Boards(_read_dir(boards_dir))
    cache = cache_dir / "depthai_boards.tar.gz"
    try:
        data = _fetch_archive()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    except OSError:
        data = cache.read_bytes() if cache.exists() else b""
    try:
        return Boards(_read_archive(data))
    except tarfile.TarError:  # empty (no cache) or corrupt
        return Boards({})


def board_from_device(features: Sequence, calibration: dai.CalibrationHandler) -> dict:
    """"From device" board: the connected sockets with the EEPROM extrinsics and hfov (else a chain in socket order)."""
    eeprom = calibration.getEepromData()
    cameras: Dict[str, dict] = {}
    previous = None
    for f in sorted(features, key=lambda f: f.socket.value):
        info = eeprom.cameraData.get(f.socket)
        cam = {
            "name": f.name or f.socket.name.lower(),
            "type": f.supportedTypes[0].name.lower(),
            "hfov": info.specHfovDeg if info and info.specHfovDeg > 0 else DEFAULT_HFOV,
        }
        ext = info.extrinsics if info else None
        if ext and ext.toCameraSocket != dai.CameraBoardSocket.AUTO:
            rotation = np.asarray(ext.rotationMatrix or np.eye(3), dtype=float)
            roll = np.arctan2(rotation[2, 1], rotation[2, 2])
            pitch = -np.arcsin(np.clip(rotation[2, 0], -1, 1))
            yaw = np.arctan2(rotation[1, 0], rotation[0, 0])
            cam["extrinsics"] = {
                "to_cam": ext.toCameraSocket.name,
                "specTranslation": {
                    "x": ext.specTranslation.x,
                    "y": ext.specTranslation.y,
                    "z": ext.specTranslation.z,
                },
                "rotation": dict(zip("rpy", np.degrees([roll, pitch, yaw]).tolist())),
            }
        elif previous:
            cam["extrinsics"] = {
                "to_cam": previous,
                "specTranslation": {"x": 0, "y": 0, "z": 0},
                "rotation": {"r": 0, "p": 0, "y": 0},
            }
        cameras[f.socket.name] = cam
        previous = f.socket.name
    return {"name": eeprom.productName, "revision": eeprom.boardRev, "cameras": cameras}


def prepare(board: dict, features: Sequence) -> dict:
    """Copy of the board with the per-camera fields the setup table edits."""
    board = copy.deepcopy(board)
    connected = {f.socket.name: f for f in features}
    for socket, cam in board["cameras"].items():
        f = connected.get(socket)
        cam.update(
            connected=f is not None,
            enabled=f is not None,
            model="perspective",
            sensorName=f.sensorName if f else "",
            size=[f.width, f.height] if f else [0, 0],
            hasAutofocus=bool(f and f.hasAutofocus),
            lensPosition=DEFAULT_LENS_POSITION,
        )
        cam.setdefault("hfov", DEFAULT_HFOV)
    return board


def problems(board: dict) -> List[str]:
    """Reasons the board cannot be calibrated; empty when it is consistent."""
    cameras = board["cameras"]
    enabled = {s for s, c in cameras.items() if c.get("enabled", True)}

    def label(s: str) -> str:
        return f"{cameras[s]['name']} ({s})"

    found = [
        f"{label(s)} is enabled but not connected."
        for s in sorted(enabled)
        if not cameras[s].get("connected", True)
    ]
    found += [
        f"{label(s)} needs a horizontal FOV above 0."
        for s in sorted(enabled)
        if not cameras[s]["hfov"] > 0
    ]
    edges: Dict[str, str] = {}
    bad_edges = 0
    for s in sorted(enabled):
        to_cam = cameras[s].get("extrinsics", {}).get("to_cam")
        if to_cam in enabled:
            edges[s] = to_cam
        elif to_cam is not None:
            bad_edges += 1
            found.append(f"{label(s)} points to {to_cam}, which is missing or disabled.")
    if any(_in_cycle(s, edges) for s in edges):
        found.append("The camera extrinsics form a cycle.")
    # Cameras with no extrinsics at all (FFC boards, RAE) are standalone; the rest must share one root.
    elif not bad_edges and len({_root(s, edges) for s in {*edges, *edges.values()}}) > 1:
        found.append("The enabled cameras are not all connected by extrinsics.")
    stereo = board.get("stereo_config")
    for side in ("left_cam", "right_cam") if stereo else ():
        if stereo[side] not in enabled:
            found.append(f"The stereo {side[:-4]} camera {stereo[side]} is disabled.")
    return found


def _in_cycle(start: str, edges: Dict[str, str]) -> bool:
    node = edges.get(start)
    for _ in edges:
        if node == start:
            return True
        node = edges.get(node)
    return False


def _root(node: str, edges: Dict[str, str]) -> str:
    """End of the to_cam chain from node (the chain is acyclic here)."""
    for _ in edges:
        if node not in edges:
            break
        node = edges[node]
    return node


def _mounting_from_board(board: dict, imu_name: str, name: str) -> ImuMounting:
    sensors = list(board["imuExtrinsics"]["sensors"].values())
    if not sensors:
        raise LookupError(f"{name} has no IMU extrinsics")
    # RVC2 reports the chip (BNO086, BMI270) and boards list both options; RVC4 reports a generic
    # name ("accel"), and its boards list the accel/gyro chip first, before the magnetometer.
    sensor = next(
        (
            s
            for s in sensors
            if imu_name.startswith(s["name"]) or s["name"].startswith(imu_name)
        ),
        sensors[0],
    )
    extrinsics = sensor["extrinsics"]
    translation = [float(extrinsics["specTranslation"][axis]) for axis in "xyz"]
    return ImuMounting(
        socket=dai.CameraBoardSocket.__members__[extrinsics["to_cam"]],
        translation_cm=translation,
        spec_translation_cm=translation,
        spec_rotation=np.asarray(extrinsics["rotationMatrix"], dtype=float),
        source=f"depthai-boards {name}",
    )


def _mounting_from_eeprom(eeprom: dai.EepromData, source: str) -> ImuMounting:
    extrinsics = eeprom.imuExtrinsics
    socket = extrinsics.toCameraSocket
    if socket == dai.CameraBoardSocket.AUTO:
        socket = dai.CameraBoardSocket.CAM_A
    return ImuMounting(
        socket=socket,
        translation_cm=[
            extrinsics.translation.x,
            extrinsics.translation.y,
            extrinsics.translation.z,
        ],
        spec_translation_cm=[
            extrinsics.specTranslation.x,
            extrinsics.specTranslation.y,
            extrinsics.specTranslation.z,
        ],
        spec_rotation=None,
        source=source,
    )


if __name__ == "__main__":
    # Self-check: python3 -m utils.board_config [--boards-dir DEPTHAI_BOARDS_DIR]
    import argparse
    import tempfile
    from types import SimpleNamespace

    parser = argparse.ArgumentParser()
    parser.add_argument("--boards-dir", type=Path)
    args = parser.parse_args()
    boards = load_boards(args.boards_dir, Path(tempfile.mkdtemp()))
    assert len(boards.names) >= 60, f"only {len(boards.names)} boards loaded"

    def connect(board: dict) -> dict:
        return prepare(
            board,
            [
                SimpleNamespace(
                    socket=dai.CameraBoardSocket.__members__[s],
                    sensorName="X",
                    width=1280,
                    height=800,
                    hasAutofocus=False,
                )
                for s in board["cameras"]
            ],
        )

    for name in boards.names:
        found = problems(connect(boards.get(name)))
        # Board data bug: this file's stereo chain points to CAM_A, which it does not list.
        known = ["right (CAM_C) points to CAM_A, which is missing or disabled."]
        assert found == (known if name == "OAK-D-W-POE-C57.json" else []), (name, found)

    def eeprom(product: str, board: str) -> SimpleNamespace:
        return SimpleNamespace(productName=product, boardName=board)

    assert boards.detect(eeprom("OAK-D-PRO-AF", "DM9098"), "") == "OAK-D-PRO.json"
    assert boards.detect(eeprom("OAK-4-D-FF", "NG9498-ASM"), "") == "OAK-4-D.json"
    assert boards.detect(eeprom("x", "y"), "OAK-D-PRO-AF") == "OAK-D-PRO.json"  # by name
    assert boards.detect(eeprom("x", "y"), "nope") is None

    pro = connect(boards.get("OAK-D-PRO.json"))
    cycle = copy.deepcopy(pro)
    cycle["cameras"]["CAM_A"]["extrinsics"] = copy.deepcopy(pro["cameras"]["CAM_C"]["extrinsics"])
    cycle["cameras"]["CAM_A"]["extrinsics"]["to_cam"] = "CAM_C"
    missing = copy.deepcopy(pro)
    missing["cameras"]["CAM_B"]["extrinsics"]["to_cam"] = "CAM_Z"
    stereo = copy.deepcopy(pro)
    stereo["cameras"]["CAM_B"]["enabled"] = False
    for broken in (cycle, missing, stereo):
        assert len(problems(broken)) == 1, problems(broken)
    print(f"board config self-check passed ({len(boards.names)} boards)")
