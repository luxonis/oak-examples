import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
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
    parser.add_argument(
        "-m",
        "--model",
        help="Name of the model to use: yolo-world or yoloe",
        required=False,
        default="yoloe",
        type=str,
        choices=["yolo-world", "yoloe"],
    )
    parser.add_argument(
        "--precision",
        help="Model precision for YOLOE models: int8 (faster) or fp16 (more accurate).",
        required=False,
        default="fp16",
        type=str,
        choices=["int8", "fp16"],
    )
    parser.add_argument(
        "--semantic_seg",
        help="Display output as semantic segmentation otherwise use instance segmentation (only applicable for YOLOE).",
        action="store_true",
    )

    args = parser.parse_args()

    return parser, args
