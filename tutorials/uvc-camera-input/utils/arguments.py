import argparse
import os


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


def fourcc(value: str) -> str:
    if value and len(value) != 4:
        raise argparse.ArgumentTypeError(
            "FOURCC values must be exactly four characters"
        )
    return value


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-d",
        "--device",
        help="Optional name, DeviceID, or IP of the DepthAI device to connect to.",
        required=False,
        default=os.getenv("DEPTHAI_DEVICE"),
        type=str,
    )
    parser.add_argument(
        "--uvc-device",
        help="UVC source to open. Use 'auto', a Linux path like /dev/video2, or an OpenCV index like 0.",
        required=False,
        default=os.getenv("UVC_DEVICE", "auto"),
        type=str,
    )
    parser.add_argument(
        "--width",
        help="Requested UVC capture width.",
        required=False,
        default=env_int("UVC_WIDTH", 1920),
        type=int,
    )
    parser.add_argument(
        "--height",
        help="Requested UVC capture height.",
        required=False,
        default=env_int("UVC_HEIGHT", 1080),
        type=int,
    )
    parser.add_argument(
        "--fps",
        help="Requested UVC capture FPS.",
        required=False,
        default=env_int("UVC_FPS", 5),
        type=int,
    )
    parser.add_argument(
        "--fourcc",
        help="Optional camera FOURCC request, for example MJPG or YUYV.",
        required=False,
        default=os.getenv("UVC_FOURCC", ""),
        type=fourcc,
    )
    parser.add_argument(
        "--buffer-size",
        help="Requested OpenCV capture buffer size. Use 0 to keep the backend default.",
        required=False,
        default=env_int("UVC_BUFFER_SIZE", 4),
        type=int,
    )
    parser.add_argument(
        "--output-width",
        help="ImageManip output width. Defaults to the requested capture width.",
        required=False,
        default=env_optional_int("UVC_OUTPUT_WIDTH"),
        type=int,
    )
    parser.add_argument(
        "--output-height",
        help="ImageManip output height. Defaults to the requested capture height.",
        required=False,
        default=env_optional_int("UVC_OUTPUT_HEIGHT"),
        type=int,
    )
    parser.add_argument(
        "--max-frames",
        help="Stop after this many frames. Use 0 to run until interrupted.",
        required=False,
        default=env_int("UVC_MAX_FRAMES", 0),
        type=int,
    )
    parser.add_argument(
        "--fps-log-interval",
        help="Print measured delivered FPS every N seconds. Use 0 to disable periodic logging.",
        required=False,
        default=env_float("UVC_FPS_LOG_INTERVAL", 5.0),
        type=float,
    )
    parser.add_argument(
        "--http-port",
        help="HTTP port used by the DepthAI Visualizer connection.",
        required=False,
        default=env_int("DEPTHAI_VISUALIZER_HTTP_PORT", 8082),
        type=int,
    )

    args = parser.parse_args()
    return parser, args
