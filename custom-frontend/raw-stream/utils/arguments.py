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
        "--fps-limit",
        help="FPS limit.",
        required=False,
        default=None,
        type=int,
    )
    parser.add_argument(
        "-ip",
        "--ip",
        help="IP address to serve the frontend on.",
        required=False,
        type=str,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Port to serve the frontend on.",
        required=False,
        type=int,
    )

    args = parser.parse_args()

    return parser, args
