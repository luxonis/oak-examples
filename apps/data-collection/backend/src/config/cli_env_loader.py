import argparse


class CLIEnvLoader:
    """
    Handles environment (.env) loading and command-line argument parsing.
    """

    @staticmethod
    def parse_arguments() -> argparse.Namespace:
        """
        Private helper to initialize and parse command-line arguments.
        """
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
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
            "-api",
            "--api_key",
            help=(
                "HubAI API key to access private model. "
                "Alternatively, set 'DEPTHAI_HUB_API_KEY' environment variable."
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

        return parser.parse_args()
