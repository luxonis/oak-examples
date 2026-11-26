import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-m",
        "--model",
        help="Object detection model HubAI reference.",
        default="luxonis/yolov6-nano:r2-coco-512x288",
        type=str,
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
        "-a",
        "--axis",
        help="Axis for cumulative counting.",
        required=False,
        default="x",
        choices=["x", "y"],
        type=str,
    )

    parser.add_argument(
        "-roi",
        "--roi_position",
        help="Position of the axis (if 0.5, axis is placed in the middle of the frame).",
        required=False,
        default=0.5,
        type=float,
    )

    parser.add_argument(
        "--crossing_margin",
        help="Normalized half-width of the no-count band around the line.",
        default=0.02,
        type=float,
    )

    parser.add_argument(
        "--track_labels",
        help="Model class IDs to count. By default, count every detected class.",
        nargs="+",
        type=int,
    )

    parser.add_argument(
        "--show_raw_detections",
        help="Show raw detector boxes in the Visualizer alongside tracked boxes.",
        action="store_true",
    )

    args = parser.parse_args()

    if args.track_labels is not None and any(label < 0 for label in args.track_labels):
        parser.error("--track_labels IDs must be non-negative")

    return parser, args
