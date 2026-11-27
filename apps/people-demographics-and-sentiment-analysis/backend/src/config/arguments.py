import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Useful ONLY for running in Peripheral mode
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
        "--no-frontend", action="store_true", help="Use a separate frontend server."
    )
    parser.add_argument(
        "--frontend-dir", help="Directory containing the built frontend index.html."
    )
    parser.add_argument(
        "--frontend-host", default="127.0.0.1", help="Frontend bind address."
    )
    parser.add_argument(
        "--frontend-port", type=int, default=8082, help="Frontend HTTP port."
    )

    args = parser.parse_args()

    return parser, args
