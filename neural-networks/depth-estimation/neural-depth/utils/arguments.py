import argparse
import depthai as dai


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-m",
        "--model",
        help="Model variant to use. One of `['NANO', 'SMALL', 'MEDIUM', 'LARGE']`. Defaults to 'LARGE'.",
        required=False,
        default="LARGE",
        choices=["NANO", "SMALL", "MEDIUM", "LARGE"],
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

    args = parser.parse_args()
    MODEL_VARIANT_MAP = {
        "NANO": dai.DeviceModelZoo.NEURAL_DEPTH_NANO,
        "SMALL": dai.DeviceModelZoo.NEURAL_DEPTH_SMALL,
        "MEDIUM": dai.DeviceModelZoo.NEURAL_DEPTH_MEDIUM,
        "LARGE": dai.DeviceModelZoo.NEURAL_DEPTH_LARGE,
    }
    args.model = MODEL_VARIANT_MAP[args.model]
    return parser, args
