import argparse


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-fps", "--fps_limit", type=positive_int, default=10, help="Camera FPS"
    )
    parser.add_argument(
        "-is",
        "--input_size",
        choices=["2160p", "1080p", "720p", "480p", "360p"],
        default="360p",
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        help="Device IDs or IPs in left-to-right order; first device runs inference",
    )
    parser.add_argument(
        "--sockets",
        nargs="+",
        choices=[f"CAM_{letter}" for letter in "ABCDEFGH"],
        default=["CAM_A"],
        help="Sockets on each selected device",
    )
    parser.add_argument(
        "--sync-threshold-ms",
        type=positive_int,
        default=100,
        help="Maximum capture-time spread; software sync does not align exposures",
    )
    parser.add_argument("--estimation-frames", type=positive_int, default=3)
    parser.add_argument(
        "--max-panorama-size",
        nargs=2,
        type=positive_int,
        default=[4096, 2048],
        metavar=("WIDTH", "HEIGHT"),
    )
    parser.add_argument(
        "--seam-finder",
        choices=[
            "NONE",
            "VORONOI",
            "DP_COLOR",
            "DP_COLOR_GRAD",
            "GRAPHCUT_COLOR",
            "GRAPHCUT_COLOR_GRAD",
        ],
        default="DP_COLOR",
    )
    parser.add_argument(
        "--no-nn",
        action="store_true",
        help="Validate camera/stitching only, without downloading a model",
    )
    parser.add_argument(
        "--duration",
        type=positive_int,
        help="Stop after this many seconds; fail if no panorama was produced",
    )
    parser.add_argument(
        "--reset-after",
        type=positive_int,
        help="Reset registration once after this many seconds",
    )
    return parser, parser.parse_args()
