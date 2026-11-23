"""Calibrate and validate a recorded dataset offline (no device).

python3 process_dataset.py DATASET --board OAK-D-PRO.json -nx 29 -ny 29 -s 5.0 -ms 3.7
"""

import argparse
import json
import sys
from pathlib import Path

from utils.camera_calibration import CalibrationError, calibrate_rig
from utils.charuco import BoardSpec, load_dataset
from utils.validation import report


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("dataset", type=Path)
    p.add_argument("--board", type=Path, required=True, help="depthai-boards JSON")
    p.add_argument("-nx", type=int, required=True, help="squares in X")
    p.add_argument("-ny", type=int, required=True, help="squares in Y")
    p.add_argument("-s", type=float, required=True, help="square size, cm")
    p.add_argument("-ms", type=float, required=True, help="marker size, cm")
    p.add_argument("--dictionary", default="DICT_4X4_1000")
    p.add_argument("--old-calib", type=Path, help="eepromToJson file to compare against")
    p.add_argument("--fisheye", nargs="*", default=[], metavar="NAME", help="cameras to fit as fisheye")
    p.add_argument("--out", type=Path, help="write the report JSON here")
    args = p.parse_args()

    spec = BoardSpec(args.nx, args.ny, args.s, args.ms, args.dictionary)
    if spec.problem():
        sys.exit(spec.problem())
    cfg = json.loads(args.board.read_text())
    cfg = cfg.get("board_config", cfg)
    for cam in cfg["cameras"].values():
        cam["enabled"] = (args.dataset / cam["name"]).is_dir()
        cam["model"] = "fisheye" if cam["name"] in args.fisheye else "perspective"
    names = {s: c["name"] for s, c in cfg["cameras"].items() if c["enabled"]}

    def progress(fraction: float, stage: str) -> None:
        print(f"\r{fraction:4.0%} {stage:<40}", end="", file=sys.stderr, flush=True)

    obs = load_dataset(args.dataset, names, spec, progress)
    try:
        new = calibrate_rig(cfg, obs, spec, progress)
    except CalibrationError as e:
        print(f"\nCalibration failed: {e}")
        return 1
    old = None
    if args.old_calib:
        import depthai as dai

        from utils.eeprom import rig_from_handler

        handler = dai.CalibrationHandler.fromJson(json.loads(args.old_calib.read_text()))
        old = rig_from_handler(handler, cfg, {s: c.size for s, c in new.cameras.items()})
    result = report(new, old, cfg, obs, spec)
    print(" " * 60, file=sys.stderr)

    name = {s: c["name"] for s, c in cfg["cameras"].items()}
    print(f"{'camera':<10}{'model':<12}{'views':>6}{'coverage':>10}{'rms old':>9}{'rms new':>9}")
    for c in result["cameras"]:
        print(f"{c['name']:<10}{c['model']:<12}{c['views']:>6}{c['coverage']:>10.0%}"
              f"{_fmt(c['rmsOld']):>9}{_fmt(c['rmsNew']):>9}")
    print(f"\n{'cross-camera':<20}{'views':>6}{'old px':>9}{'new px':>9}")
    for r in result["pairs"]:
        print(f"{name[r['from']] + ' -> ' + name[r['to']]:<20}{r['views']:>6}"
              f"{_fmt(r['oldPx']):>9}{_fmt(r['newPx']):>9}")
    if result["stereo"]:
        s = result["stereo"]
        print(f"\nepipolar {name[s['left']]} / {name[s['right']]}: "
              f"old {_fmt(s['epipolarOld'])} px, new {_fmt(s['epipolarNew'])} px")
    for w in result["warnings"]:
        print("warning:", w)
    for pr in result["problems"]:
        print("problem:", pr)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2))
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
