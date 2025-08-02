import argparse


def initialize_argparser():
    """Initialize the argument parser for the script."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.description = "This example demonstrates how stereo pipeline works on the OAK device (using depthai). It rectifies mono frames (receives from the OAK camera) and then uses cv2.StereoSGBM to calculate the disparity on the host. It also colorizes the disparity and shows it to the user."

    parser.add_argument(
        "-d",
        "--device",
        help="Optional name, DeviceID or IP of the camera to connect to.",
        required=False,
        default=None,
        type=str,
    )

    args = parser.parse_args()

    return parser, args
