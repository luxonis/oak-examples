import argparse


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-d", "--device", help="Device ID or IP of the camera.")
    parser.add_argument(
        "--no-frontend", action="store_true", help="Use a separate frontend server."
    )
    parser.add_argument(
        "--frontend-dir", help="Directory containing the built frontend index.html."
    )
    parser.add_argument(
        "--frontend-host", default="127.0.0.1", help="Frontend bind address."
    )
    parser.add_argument(
        "--frontend-port", type=int, default=8082, help="Frontend HTTP port."
    )

    return parser, parser.parse_args()
