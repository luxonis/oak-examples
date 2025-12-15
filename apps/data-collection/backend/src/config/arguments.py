from argparse import Namespace, ArgumentParser, ArgumentDefaultsHelpFormatter


def initialize_argparser() -> Namespace:
    """Initialize the argument parser for the script."""
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-fps",
        "--fps_limit",
        help="FPS limit for the model runtime.",
        required=False,
        default=None,
        type=int,
    )

    parser.add_argument(
        "-api",
        "--api_key",
        help="HubAI API key to access private model. Can also use 'DEPTHAI_HUB_API_KEY' environment variable instead.",
        required=False,
        default="",
        type=str,
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
