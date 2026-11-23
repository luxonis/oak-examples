import argparse
import os
from pathlib import Path


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Guided six-pose IMU calibration. Computes the IMU -> camera rotation and the accelerometer and "
        "gyroscope [Q|b] calibration, then flashes them together with the depthai-boards IMU translation."
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
        help="Local depthai-boards board JSON (e.g. boards/OAK-D-PRO.json). By default it is looked up on GitHub.",
        default=None,
        type=Path,
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
    return parser, args
