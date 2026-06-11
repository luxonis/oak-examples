import argparse


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Interactive multi-camera calibration example with visualizer and OpenCV modes."
    )

    parser.add_argument(
        "-d",
        "--device",
        help="Optional device name, DeviceID, or IP address.",
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "-fps",
        "--fps_limit",
        help="FPS limit for preview streams.",
        required=False,
        default=10,
        type=int,
    )

    parser.add_argument(
        "--ws-port",
        help="WebSocket port for the custom frontend connection.",
        required=False,
        default=8766,
        type=int,
    )

    parser.add_argument(
        "--http-port",
        help="HTTP port used when serving the stock visualizer frontend.",
        required=False,
        default=8082,
        type=int,
    )

    return parser, parser.parse_args()
