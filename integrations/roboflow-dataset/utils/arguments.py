import argparse


def range_limited_float_type(min: float, max: float | None):
    if max is None:
        max = float("inf")

    if min is None:
        min = -float("inf")

    def _range_limited_float_type_inner(arg):
        """Type function for argparse - a float within some predefined bounds"""
        try:
            f = float(arg)
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
        "--fps_limit",
        help="FPS limit for the model runtime.",
        required=False,
        default=None,
        type=int,
    )

    parser.add_argument(
        "-media",
        "--media_path",
        help="Path to the media file you aim to run the model on. If not set, the model will run on the camera input.",
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "-key",
        "--api-key",
        help="private API key copied from app.roboflow.com",
        required=True,
    )

    parser.add_argument(
        "--workspace", help="Name of the workspace in app.roboflow.com", required=True
    )

    parser.add_argument(
        "--dataset", help="Name of the project in app.roboflow.com", required=True
    )

    parser.add_argument(
        "--auto-interval",
        help="Automatically upload annotations every [SECONDS] seconds",
        required=False,
        default=None,
        type=range_limited_float_type(1, None),
    )

    parser.add_argument(
        "--auto-threshold",
        help="Automatically upload annotations with confidence above [THRESHOLD] (when used with --auto-interval)",
        required=False,
        default=0.5,
        type=range_limited_float_type(0, 1),
    )

    args = parser.parse_args()

    return parser, args
