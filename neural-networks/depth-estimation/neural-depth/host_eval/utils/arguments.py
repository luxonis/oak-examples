import argparse


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-m",
        "--model",
        help="Model variant to use. One of `['NANO', 'SMALL', 'MEDIUM', 'LARGE']`.",
        required=False,
        default="LARGE",
        choices=["NANO", "SMALL", "MEDIUM", "LARGE"],
        type=str,
    )

    parser.add_argument(
        "--dataset",
        help="Path to the dataset folder.",
        required=False,
        default="data/imperfect",
        type=str,
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output folder for evaluation results.",
        required=False,
        default="outputs_neural_depth_eval",
        type=str,
    )

    parser.add_argument(
        "-d",
        "--device_ip",
        help="IP address of the device to connect to.",
        required=True,
        type=str,
    )

    args = parser.parse_args()

    return parser, args
