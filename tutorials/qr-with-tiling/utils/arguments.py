import argparse


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
        default=15,
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
        "-r",
        "--rows",
        help="Number of rows in the grid.",
        required=False,
        default=2,
        type=int,
    )

    parser.add_argument(
        "-c",
        "--columns",
        help="Number of columns in the grid.",
        required=False,
        default=2,
        type=int,
    )

    parser.add_argument(
        "-is",
        "--input_size",
        help="Input video stream resolution",
        required=False,
        choices=["2160p", "1080p", "720p"],
        default="1080p",
        type=str,
    )

    args = parser.parse_args()

    return parser, args
