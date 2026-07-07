import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "General example script to run a single-model DepthAI pipeline from a Model Zoo/HubAI model identifier, \
        a model descriptor/YAML, or a local .tar.xz NN archive. The script creates the pipeline and visualizations \
        for a connected OAK device. \
        If using OAK-D Lite, please set the FPS limit to 28."
    )

    parser.add_argument(
        "-m",
        "--model",
        help="Model Zoo/HubAI model identifier, model YAML/descriptor, or local .tar.xz NN archive.",
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
        "-api",
        "--api_key",
        help="HubAI API key for private Model Zoo access. Can also use 'DEPTHAI_HUB_API_KEY' environment variable instead.",
        required=False,
        default="",
        type=str,
    )

    parser.add_argument(
        "-overlay",
        "--overlay_mode",
        help="If passed, overlays model output on the input image when the output is an array (e.g., depth maps, instance segmentation masks). Otherwise, displays outputs separately.",
        required=False,
        action="store_true",
    )

    args = parser.parse_args()

    return parser, args
