import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = (
        "Run one DepthAI pipeline across multiple devices and preview every device."
    )

    parser.add_argument(
        "-d",
        "--devices",
        nargs="+",
        default=[],
        help="Device IDs or IP addresses to use. If omitted, the devices are discovered.",
    )

    parser.add_argument(
        "--include-ip",
        action="store_true",
        help="Also include IP-only cameras (e.g. OAK-4) when discovering devices",
    )

    parser.add_argument(
        "--max-devices",
        type=int,
        default=None,
        help="Limit the number of discovered devices to this count",
    )

    args = parser.parse_args()

    return parser, args
