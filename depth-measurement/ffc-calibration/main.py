from __future__ import annotations

import sys
from typing import Iterable

from utils.depthai_path import configure_depthai_path

configure_depthai_path()

import depthai as dai
import numpy as np

from utils.arguments import initialize_argparser
from utils.ffc_calibration import (
    CoordinateFrameRenderer,
    FfcCalibrationApp,
    StereoPair,
    format_socket,
)


def _device_summary(device_info: dai.DeviceInfo) -> str:
    protocol = getattr(getattr(device_info, "protocol", None), "name", "unknown")
    return f"{device_info.getDeviceId()} [{protocol}]"


def _choose_device(requested_device: str | None) -> str | None:
    if requested_device:
        print(f"Using requested device: {requested_device}")
        return requested_device

    available_devices = dai.Device.getAllAvailableDevices()
    if not available_devices:
        print("No DepthAI devices found.")
        return None

    if len(available_devices) == 1:
        selected = available_devices[0].getDeviceId()
        print(f"Found one device: {_device_summary(available_devices[0])}")
        return selected

    print("Available devices:")
    for idx, device_info in enumerate(available_devices, start=1):
        print(f"  {idx}. {_device_summary(device_info)}")

    while True:
        choice = input("Select a device by number, or press q to quit: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return None
        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        index = int(choice) - 1
        if 0 <= index < len(available_devices):
            return available_devices[index].getDeviceId()

        print("Selection out of range.")


def _baseline_text(calibration: dai.CalibrationHandler, pair: StereoPair) -> str:
    tvec = np.asarray(calibration.getCameraTranslationVector(pair.left, pair.right, False)).reshape(-1)
    distance = float(np.linalg.norm(tvec))
    return (
        f"{pair.label():<18} "
        f"baseline: {distance:7.3f} cm "
        f"translation: {np.round(tvec, 3).tolist()}"
    )


def _print_calibration_stats(
    app: FfcCalibrationApp,
    calibration: dai.CalibrationHandler,
    pairs: Iterable[StereoPair],
) -> None:
    sockets = ", ".join(format_socket(socket) for socket in app.sockets)
    print("\nCamera configuration:")
    print(f"  Detected sockets: {sockets}")
    print("  Stereo pairs:")
    for idx, pair in enumerate(pairs, start=1):
        line = f"    {idx}. {_baseline_text(calibration, pair)}"
        entered = getattr(app, "entered_baselines_cm", {}).get((pair.left, pair.right))
        if entered is not None:
            line += f" | entered baseline: {entered:.3f} cm"
        print(line)


def _run_dynamic_calibration(app: FfcCalibrationApp) -> dai.CalibrationHandler:
    print("\nEnter the baseline distances requested by the calibration flow.")
    print("These values are recorded for the selected camera chain and shown later in the menu.")
    initial_calibration = app.create_eeprom(use_device_calibration=False)

    print("\nDynamic calibration streams:")
    for socket in app.sockets:
        print(f"  preview_{format_socket(socket)}")
    print("  calibration_status")
    print("  calibration_frames")
    print("  coordinate-frame plot")

    print("\nStarting dynamic calibration. Press q inside the calibration windows to cancel.")
    calibration = app.calibrate(
        initial_calibration,
        status_label="Dynamic calibration in progress",
    )

    print("Dynamic calibration finished.")
    return calibration


def _pair_menu(app: FfcCalibrationApp, calibration: dai.CalibrationHandler) -> None:
    renderer = CoordinateFrameRenderer()

    with app.open_device():
        while True:
            pairs = app.get_all_stereo_pairs(calibration)
            if not pairs:
                raise RuntimeError("No usable stereo pair could be derived from the calibration.")

            print("\nStereo pair menu:")
            _print_calibration_stats(app, calibration, pairs)
            print("\nCommands:")
            print("  <number>  open that stereo pair preview")
            print("  f         flash the current calibration to the device")
            print("  q         quit")

            choice = input("Selection: ").strip().lower()
            if choice in {"q", "quit", "exit"}:
                return
            if choice in {"f", "flash"}:
                app.flash_calibration(calibration)
                continue
            if not choice.isdigit():
                print("Enter a pair number, f, or q.")
                continue

            index = int(choice) - 1
            if index < 0 or index >= len(pairs):
                print("Selection out of range.")
                continue

            pair = pairs[index]
            print(
                f"\nOpening {pair.label()} preview. "
                "Press q in the OpenCV window to return to the pair menu."
            )
            app.show_depth(
                pair.left,
                pair.right,
                calibration=calibration,
                live_renderer=renderer,
            )


def main() -> None:
    _, args = initialize_argparser()

    device_id = _choose_device(args.device)
    if device_id is None:
        return

    app = FfcCalibrationApp(device_id, fps=args.fps_limit)
    try:
        print(f"Connected to device: {app.deviceId}")

        calibration = _run_dynamic_calibration(app)
        _pair_menu(app, calibration)
    finally:
        app.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
