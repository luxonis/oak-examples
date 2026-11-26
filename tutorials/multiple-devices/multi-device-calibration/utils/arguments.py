import argparse
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "calibration.json"


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Estimate the relative poses of two or more OAK devices with the "
        "MultiDeviceCalibration node and save them as one calibration file."
    )

    parser.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=[],
        help="Device IDs or IP addresses to calibrate. If omitted, the devices are discovered.",
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
        "-n",
        "--sample-count",
        type=int,
        default=10,
        help="Number of synchronized image groups collected before solving",
    )

    parser.add_argument(
        "--known-distance",
        type=float,
        default=None,
        help="Measured distance in centimeters between the calibration cameras of the "
        "first two devices. Required when no device has a CAM_B/CAM_C stereo pair.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to save the calibration JSON",
    )

    args = parser.parse_args()

    return parser, args
