import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Multi-device spatial detection and Bird's Eye View (BEV) fusion application."
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

    parser.add_argument(
        "--fps_limit",
        help="FPS limit for the model runtime.",
        required=False,
        default=30,
        type=int,
    )

    args = parser.parse_args()

    return parser, args
