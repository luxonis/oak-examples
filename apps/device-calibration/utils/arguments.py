import argparse
import os
from pathlib import Path


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Guided camera and IMU calibration: ChArUco capture for intrinsics and extrinsics, a six-pose IMU "
        "capture, then one flash with an EEPROM backup."
    )
    parser.add_argument(
        "-d",
        "--device",
        help="Optional name, DeviceID or IP of the camera to connect to.",
        required=False,
        default=None,
        type=str,
    )
    parser.add_argument(
        "--board-config",
        help="Local depthai-boards board JSON (e.g. boards/OAK-D-PRO.json) to use instead of the one detected from the device.",
        default=None,
        type=Path,
    )
    parser.add_argument(
        "--boards-dir",
        help="Local depthai-boards checkout. By default the boards are fetched from GitHub (cached).",
        default=None,
        type=Path,
    )
    parser.add_argument(
        "--capture-fps",
        help="Frame rate of the live detection stream and of the full-resolution capture. "
        "The OV9282 mono sensors output black frames below 6.",
        default=6,
        type=int,
    )
    parser.add_argument(
        "--replay-dataset",
        help="Drive the capture step from a recorded dataset (folders named like the cameras) instead of the cameras.",
        default=None,
        type=Path,
    )
    parser.add_argument(
        "--dry-run",
        help="Do everything on Flash except writing to the device.",
        action="store_true",
    )
    parser.add_argument(
        "--capture-seconds",
        help="Capture duration per pose.",
        default=4.0,
        type=float,
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for calibration reports and EEPROM backups.",
        # OAKAGENT_STORAGE_APP is the persistent app storage when running standalone on RVC4.
        default=Path(os.environ.get("OAKAGENT_STORAGE_APP", "."))
        / "device_calibration_output",
        type=Path,
    )
    args = parser.parse_args()
    if args.capture_seconds < 1.0:
        parser.error("--capture-seconds must be at least 1")
    if args.capture_fps <= 0:
        parser.error("--capture-fps must be positive")
    return parser, args
