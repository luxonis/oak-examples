import argparse
import depthai as dai


NATIVE_MODELS = {
    name.removeprefix("NEURAL_DEPTH_"): model
    for name, model in dai.DeviceModelZoo.__members__.items()
    if name.startswith("NEURAL_DEPTH_")
}
LAS2_MODELS = (
    "l-fp16-1280x800",
    "l-mp-1280x800",
    "l-mp-1024x640",
    "m-mp-768x480",
    "m-mp-512x320",
)


def initialize_argparser(argv=None):
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--backend",
        choices=["native", "las2"],
        default="native",
        help="Depth backend: built-in NeuralDepth or Lite Any Stereo V2.",
    )
    parser.add_argument(
        "-m",
        "--model",
        help=(
            "Backend-specific model. Native: "
            + ", ".join(NATIVE_MODELS)
            + "; LAS2: "
            + ", ".join(LAS2_MODELS)
            + ". Defaults to LARGE (native) or l-fp16-1280x800 (LAS2)."
        ),
        required=False,
        default=None,
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

    args = parser.parse_args(argv)
    if args.fps_limit is not None and args.fps_limit <= 0:
        parser.error("--fps_limit must be positive")
    if args.backend == "native":
        args.model = (args.model or "LARGE").upper().removeprefix("NEURAL_DEPTH_")
        models = NATIVE_MODELS
    else:
        args.model = (args.model or LAS2_MODELS[0]).lower()
        models = LAS2_MODELS
    if args.model not in models:
        parser.error(
            f"Invalid model '{args.model}' for {args.backend}. Choose: {', '.join(models)}"
        )
    return parser, args
