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
        "-m",
        "--model",
        help="Model to use: 'yoloe' or 'yolo-world'",
        choices=["yoloe", "yolo-world"],
        default="yoloe",
        type=str,
    )

    parser.add_argument(
        "--semantic_seg",
        help="Display output as semantic segmentation otherwise use instance segmentation (only applicable for YOLOE).",
        action="store_true",
    )

    args = parser.parse_args()
    return args
