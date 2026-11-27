import argparse

from utils.frontend_server import DEFAULT_FRONTEND_IP, DEFAULT_FRONTEND_PORT


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
        "--no-frontend",
        help="Disable serving the static frontend bundle from Python (used in standalone oakapp mode or with Vite dev server).",
        action="store_true",
    )

    parser.add_argument(
        "--frontend-ip",
        help="IP address to serve the static frontend bundle on in peripheral mode.",
        required=False,
        default=DEFAULT_FRONTEND_IP,
        type=str,
    )

    parser.add_argument(
        "--frontend-port",
        help="Port to serve the static frontend bundle on in peripheral mode.",
        required=False,
        default=DEFAULT_FRONTEND_PORT,
        type=int,
    )

    parser.add_argument(
        "--frontend-dir",
        help="Path to the built static frontend bundle directory (overrides OAKAPP_STATIC_FRONTEND_PATH and default frontend/dist).",
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "--https",
        "--use-ssl",
        dest="use_ssl",
        help="Serve the local peripheral frontend over HTTPS using a self-signed or provided TLS certificate.",
        action="store_true",
    )

    parser.add_argument(
        "--certificate-path",
        help="Path to TLS certificate (.crt) file used when --https is enabled.",
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "--key-path",
        help="Path to TLS private key (.key) file used when --https is enabled.",
        required=False,
        default=None,
        type=str,
    )

    args = parser.parse_args()

    return parser, args
