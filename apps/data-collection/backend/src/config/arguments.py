from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, Namespace


def parse_args() -> Namespace:
    """
    Define and parse CLI arguments for the application.
    """
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-fps",
        "--fps_limit",
        help="FPS limit for the pipeline runtime.",
        required=False,
        default=None,
        type=int,
    )

    parser.add_argument(
        "-api",
        "--api_key",
        help=(
            "HubAI API key to access private model. "
            "Alternatively, set 'DEPTHAI_HUB_API_KEY' env var."
        ),
        required=False,
        default="",
        type=str,
    )

    parser.add_argument(
        "-media",
        "--media_path",
        help=(
            "Path to the media file to run the model on. "
            "If not set, the model runs on the live camera input."
        ),
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument("-d", "--device", help="Device ID or IP of the camera.")

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
    return args
