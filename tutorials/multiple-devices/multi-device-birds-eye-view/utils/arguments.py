import argparse
from pathlib import Path

DEFAULT_CALIBRATION = Path(__file__).resolve().parent.parent / "calibration.json"


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = "Calibrate multiple OAK devices, fit the ground plane to their merged point cloud and project the cameras onto it."

    parser.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=[],
        help="Device IDs or IP addresses to use. If omitted, the devices are discovered.",
    )

    parser.add_argument(
        "--include-ip",
        action="store_true",
        help="Also include IP-only cameras (e.g. OAK-4) when discovering devices",
    )

    parser.add_argument(
        "--max-devices",
        type=int,
        default=None,
        help="Limit the number of discovered devices to this count",
    )

    parser.add_argument(
        "-c",
        "--calibration",
        type=Path,
        default=DEFAULT_CALIBRATION,
        help="Multi-device calibration JSON. It is created on the first run.",
    )

    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Calibrate again even if the calibration file exists",
    )

    parser.add_argument(
        "-n",
        "--sample-count",
        type=int,
        default=10,
        help="Number of synchronized image groups collected for the calibration",
    )

    parser.add_argument(
        "--known-distance",
        type=float,
        default=None,
        help="Measured distance in centimeters between the calibration cameras of the "
        "first two devices. Required when no device has a CAM_B/CAM_C stereo pair.",
    )

    parser.add_argument(
        "--fps_limit",
        help="FPS limit of the cameras.",
        required=False,
        default=10,
        type=int,
    )

    parser.add_argument(
        "--max-range",
        type=float,
        default=4.0,
        help="Distance in meters from a camera beyond which the ground is not drawn",
    )

    args = parser.parse_args()

    return parser, args
