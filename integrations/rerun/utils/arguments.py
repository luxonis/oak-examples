import argparse
from typing import Optional


def range_limited_int_type(min: int, max: Optional[int]):
    if max is None:
        max = float("inf")

    if min is None:
        min = -float("inf")

    def _range_limited_float_type_inner(arg):
        """Type function for argparse - a float within some predefined bounds"""
        try:
            f = int(arg)
        except ValueError:
            raise argparse.ArgumentTypeError("Must be a floating point number")
        if f < min or f > max:
            raise argparse.ArgumentTypeError(
                f"Argument must be in range ({min}, {max})"
            )
        return f

    return _range_limited_float_type_inner


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
        help="FPS limit.",
        required=False,
        default=None,
        type=int,
    )

    parser.add_argument(
        "-l",
        "--left",
        default=False,
        action="store_true",
        help="Enable left camera stream.",
    )
    parser.add_argument(
        "-r",
        "--right",
        default=False,
        action="store_true",
        help="Enable right camera stream.",
    )
    parser.add_argument(
        "-pc",
        "--pointcloud",
        default=False,
        action="store_true",
        help="Enable pointcloud stream.",
    )
    parser.add_argument(
        "-s",
        "--serve",
        help="Serve the Rerun viewer using a web server on a specified port, instead of a local viewer.",
        required=False,
        default=None,
        type=range_limited_int_type(1, 65535),
    )

    args = parser.parse_args()

    return parser, args
