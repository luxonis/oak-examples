import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser()
    parser.description = (
        "Two-stage OCR example with upright text crops and text annotations. "
        "Use an OAK device or a replay video."
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
        "-media",
        "--media_path",
        help="Path to the media file you aim to run the model on. If not set, the model will run on the camera input.",
        required=False,
        default=None,
        type=str,
    )
    parser.add_argument(
        "--detection_confidence",
        type=float,
        default=0.5,
        help="Minimum detector confidence for a text crop (default: 0.5).",
    )
    parser.add_argument(
        "--min_crop_width",
        type=int,
        default=50,
        help="Minimum expanded text-box width in source pixels (default: 50).",
    )
    parser.add_argument(
        "--min_crop_height",
        type=int,
        default=12,
        help="Minimum expanded text-box height in source pixels (default: 12).",
    )
    parser.add_argument(
        "--recognition_confidence",
        type=float,
        default=0.25,
        help="Minimum recognition confidence shown in overlays (default: 0.25).",
    )
    parser.add_argument(
        "--min_text_length",
        type=int,
        default=1,
        help="Minimum recognized text length shown in overlays (default: 1).",
    )
    args = parser.parse_args()

    if not 0 <= args.detection_confidence <= 1:
        parser.error("--detection_confidence must be between 0 and 1")
    if not 0 <= args.recognition_confidence <= 1:
        parser.error("--recognition_confidence must be between 0 and 1")
    if args.min_crop_width < 1 or args.min_crop_height < 1:
        parser.error("--min_crop_width and --min_crop_height must be positive")
    if args.min_text_length < 1:
        parser.error("--min_text_length must be positive")

    return parser, args
