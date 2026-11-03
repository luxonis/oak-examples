import argparse


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        required=True,
        help="Device IDs or IPs in left-to-right order (e.g. --devices LEFT_IP RIGHT_IP); first device runs inference",
    )
    parser.add_argument(
        "--sockets",
        nargs="+",
        default=["CAM_A"],
        choices=[f"CAM_{letter}" for letter in "ABCDEFGH"],
        help="Sockets on every selected device; CAM_A selects one camera per device",
    )
    parser.add_argument("-fps", "--fps_limit", type=int, default=10)
    parser.add_argument(
        "--show-inputs",
        action="store_true",
        help="Show individual camera streams alongside the stitched panorama for debugging",
    )
    parser.add_argument(
        "-is",
        "--input_size",
        default="360p",
        choices=["2160p", "1080p", "720p", "480p", "360p"],
    )
    args = parser.parse_args()
    if args.fps_limit <= 0:
        parser.error("FPS must be greater than zero")
    return parser, args
