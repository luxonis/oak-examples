import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "This script sets up a calibration pipeline for DepthAI devices."
    )

    parser.add_argument(
        "--include-ip",
        action="store_true",
        help="Also include IP-only cameras (e.g. OAK-4) in the device list",
    )

    parser.add_argument(
        "--max-devices",
        type=int,
        default=None,
        help="Limit the total number of devices to this count",
    )

    args = parser.parse_args()

    return parser, args
