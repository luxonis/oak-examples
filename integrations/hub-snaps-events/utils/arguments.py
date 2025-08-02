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
        "-key",
        "--api_key",
        help="HubAI API key of your team. Not required if 'DEPTHAI_HUB_API_KEY' environment variable is set.",
        required=False,
        default="",
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
        "-thr",
        "--confidence_threshold",
        help="If detection is higher then set confidence then we send the snap.",
        required=False,
        default=0.7,
        type=float,
    )

    parser.add_argument(
        "-c",
        "--class_names",
        type=str,
        nargs="+",
        default=["person"],
        help="Class names to consider.",
    )

    parser.add_argument(
        "-ti",
        "--time_interval",
        help="Minimum time between snaps.",
        required=False,
        default=60.0,
        type=float,
    )
    args = parser.parse_args()

    return parser, args
