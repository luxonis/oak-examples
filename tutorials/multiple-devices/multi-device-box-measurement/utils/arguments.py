import argparse
from pathlib import Path

DEFAULT_CALIBRATION = Path(__file__).resolve().parent.parent / "calibration.json"


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Measure boxes seen by one or more OAK devices, with the support plane "
        "found automatically."
    )

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
        help="Multi-device calibration JSON. It is created on the first run with "
        "two or more devices.",
    )

    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run the multi-device calibration again even if the calibration file exists",
    )

    parser.add_argument(
        "-n",
        "--sample-count",
        type=int,
        default=10,
        help="Number of synchronized image groups collected for the multi-device calibration",
    )

    parser.add_argument(
        "--ptp",
        action="store_true",
        help="Capture on the PTP clock, so that moving boxes are measured correctly. "
        "Without it, the frames of all devices are grouped within half a frame "
        "period, and only static boxes are measured correctly.",
    )

    parser.add_argument(
        "--fps_limit",
        help="FPS limit of the cameras.",
        required=False,
        default=10,
        type=int,
    )

    args = parser.parse_args()

    return parser, args
