import argparse


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return value


def _limit(text: str) -> int:
    """A RecordControl limit. Below 0 disables it. 0 is rejected."""
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if value == 0:
        raise argparse.ArgumentTypeError(
            "0 makes RecordControl ignore the start. Use -1 to leave the limit off."
        )
    return value


def _pretrigger(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("pretrigger frames must be 0 or greater")
    return value


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=(
            "Preview a camera and record H.264 clips with RecordVideo. "
            "Press r in the visualizer to start or stop. "
            "A detection script can start a clip when a person or a face is visible "
            "and stop it after 2 seconds without that detection, or when a segment limit is reached."
        ),
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
        help="Camera, detector, and recorded file frame rate.",
        required=False,
        default=None,
        type=_positive_int,
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory that receives the recording when the pipeline stops.",
        required=False,
        default="recordings",
        type=str,
    )

    parser.add_argument(
        "--pretrigger-frames",
        help="Newest idle frames written at the next start. 0 keeps none.",
        required=False,
        default=60,
        type=_pretrigger,
    )

    parser.add_argument(
        "--max-frames",
        help="Maximum frames in one segment, including pre-trigger frames. -1 disables the limit.",
        required=False,
        default=-1,
        type=_limit,
    )

    parser.add_argument(
        "--max-duration-ms",
        help="Maximum segment length in milliseconds, measured from the moment start is applied. -1 disables the limit.",
        required=False,
        default=-1,
        type=_limit,
    )

    parser.add_argument(
        "--max-size-kb",
        help=(
            "Maximum written frame payload in 1024-byte units. "
            "The frame that reaches the limit is kept. Container bytes are not counted. "
            "-1 disables the limit."
        ),
        required=False,
        default=-1,
        type=_limit,
    )

    parser.add_argument(
        "--target",
        choices=["person", "face"],
        default="person",
        help="Default detector and label. person uses YOLOv6 COCO. face uses YuNet.",
    )

    parser.add_argument(
        "-m",
        "--model",
        help="Model Zoo slug, YAML, or descriptor used instead of the --target model.",
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "--label",
        help=(
            "Detection label that arms auto recording. "
            "Comma-separated labels are allowed. "
            "Defaults to person or face based on --target."
        ),
        required=False,
        default=None,
        type=str,
    )

    parser.add_argument(
        "--auto-record",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Build the script node that starts a recording on a matching detection "
            "and stops it after 2 seconds with no match. "
            "--no-auto-record leaves detection on screen and records only from the r key."
        ),
    )

    args = parser.parse_args()

    return parser, args
