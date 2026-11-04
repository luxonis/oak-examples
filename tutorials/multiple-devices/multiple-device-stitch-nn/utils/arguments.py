import argparse
from pathlib import Path

DEFAULT_CALIBRATION = Path(__file__).resolve().parents[1] / "calibration.json"


def initialize_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        required=True,
        help="At least two device IDs or IPs; CAM_A of each device becomes one panorama source",
    )
    parser.add_argument(
        "--calibration",
        default=str(DEFAULT_CALIBRATION),
        help="Multi-device calibration JSON; created with MultiDeviceCalibration when missing",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Redo the calibration even if the calibration file exists",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=10,
        help="Synchronized image groups the calibration collects before solving",
    )
    parser.add_argument(
        "--known-distance",
        type=float,
        help="Measured distance in cm between the first cameras of the first two devices; "
        "needed for metric scale only when no device has a factory stereo pair",
    )
    parser.add_argument(
        "-fps",
        "--fps_limit",
        type=int,
        default=10,
        help="Camera, detection and panorama rate",
    )
    parser.add_argument(
        "--projection",
        choices=["Cylindrical", "Equirectangular", "Perspective"],
        default="Cylindrical",
        help="Panorama projection; Perspective requires a combined field of view below 180 degrees",
    )
    parser.add_argument(
        "--average",
        action="store_true",
        help="Average duplicate boxes from different cameras instead of keeping one (NMS)",
    )
    parser.add_argument(
        "--blend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Seam estimation, exposure compensation and multiband blending; --no-blend copies views directly",
    )
    parser.add_argument(
        "--panorama-scale",
        type=int,
        choices=range(1, 5),
        default=2,
        help="Multiplier of the 640x400 camera views sent to the host for stitching",
    )
    parser.add_argument(
        "--sync-threshold-ms",
        type=int,
        help="Maximum timestamp spread when grouping frames and detections (default: one frame period)",
    )
    parser.add_argument(
        "--show-inputs",
        action="store_true",
        help="Also show every camera view with its own detections",
    )
    args = parser.parse_args()
    if len(args.devices) < 2:
        parser.error("at least two devices are required")
    if args.fps_limit <= 0:
        parser.error("FPS must be greater than zero")
    if args.sync_threshold_ms is None:
        args.sync_threshold_ms = 1000 // args.fps_limit
    if not 0 < args.sync_threshold_ms <= 1000 / args.fps_limit:
        parser.error(
            f"sync threshold must be positive and at most one frame period ({1000 / args.fps_limit:.1f} ms)"
        )
    if args.known_distance is not None and args.known_distance <= 0:
        parser.error("known distance must be positive")
    return parser, args
