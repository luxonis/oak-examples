import argparse

import rerun as rr


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
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
        "-fps",
        "--fps-limit",
        help="FPS limit. Defaults to 20 on RVC2 and 30 on RVC4.",
        required=False,
        default=None,
        type=int,
    )

    rr.script_add_args(parser)

    args = parser.parse_args()

    return parser, args
