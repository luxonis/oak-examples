import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-fps",
        "--fps_limit",
        help="FPS limit for the model runtime.",
        required=False,
        default=20,
        type=int,
    )

    parser.add_argument(
        "-is",
        "--input_size",
        help="Input video stream resolution",
        required=False,
        choices=["2160p", "1080p", "720p", "480p", "360p"],
        default="360p",
        type=str,
    )

    args = parser.parse_args()

    return parser, args
