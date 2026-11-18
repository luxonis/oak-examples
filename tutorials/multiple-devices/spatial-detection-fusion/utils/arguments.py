import argparse
from pathlib import Path

DEFAULT_CALIBRATION = Path(__file__).resolve().parents[1] / "calibration.json"


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Multi-device spatial detection and Bird's Eye View (BEV) fusion application."
    )

    parser.add_argument(
        "-c",
        "--calibration",
        type=Path,
        default=DEFAULT_CALIBRATION,
        help="Calibration JSON saved by the multi-device-calibration example",
    )

    parser.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=[],
        help="Device IDs or IP addresses to use. If omitted, every device in the calibration is used.",
    )

    parser.add_argument(
        "--fps_limit",
        help="FPS limit for the model runtime.",
        required=False,
        default=30,
        type=int,
    )

    args = parser.parse_args()

    return parser, args
