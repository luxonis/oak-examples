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
        "-c",
        "--class_names",
        type=str,
        nargs="+",
        default=["person", "chair", "TV"],
        help="Class names to be detected",
    )

    parser.add_argument(
        "-conf",
        "--confidence_thresh",
        help="Sets the confidence threshold",
        default=0.1,
        type=float,
    )

    args = parser.parse_args()

    return parser, args
