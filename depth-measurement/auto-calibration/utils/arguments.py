import argparse


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def initialize_argparser():
    parser = argparse.ArgumentParser(
        description="Automatic runtime stereo calibration on OAK devices.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d", "--device", help="Optional device name, ID or IP address."
    )
    parser.add_argument(
        "-fps",
        "--fps_limit",
        type=positive_int,
        default=10,
        help="Stereo camera FPS limit.",
    )
    parser.add_argument(
        "--mode",
        choices=("on-start", "continuous"),
        default="on-start",
        help="When to run automatic calibration. Updates stay in RAM.",
    )
    parser.add_argument(
        "--auto-interval",
        type=positive_int,
        default=30,
        help="Seconds to pause after each continuous calibration cycle.",
    )
    return parser, parser.parse_args()
