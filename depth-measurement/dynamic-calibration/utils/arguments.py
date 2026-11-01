import argparse


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def initialize_argparser(argv=None):
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Manual or automatic runtime stereo calibration on OAK devices."
    )

    parser.add_argument(
        "--mode",
        choices=("manual", "on-start", "continuous"),
        default="manual",
        help="Calibration workflow. Automatic modes update RAM only, never EEPROM.",
    )
    parser.add_argument(
        "--auto-interval",
        type=positive_int,
        default=30,
        help="Seconds between calibration cycles in continuous mode.",
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
        help="Stereo camera FPS limit.",
        required=False,
        default=10,
        type=positive_int,
    )

    args = parser.parse_args(argv)

    return parser, args
