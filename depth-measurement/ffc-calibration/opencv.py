import cv2 as cv
import numpy as np

from utils.depthai_path import configure_depthai_path

configure_depthai_path()

import depthai as dai

from utils.arguments import initialize_argparser
from utils.ffc_calibration import (
    CoordinateFrameRenderer,
    FfcCalibrationApp,
    StereoPair,
    format_socket,
)


def render_dashboard(
    app: FfcCalibrationApp,
    calibration: dai.CalibrationHandler,
    selected_pair: StereoPair,
) -> np.ndarray:
    width, height = 1280, 720
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (20, 20, 24)

    header = "Multi-camera calibration"
    cv.putText(
        canvas,
        header,
        (40, 60),
        cv.FONT_HERSHEY_SIMPLEX,
        1.4,
        (255, 255, 255),
        3,
        cv.LINE_AA,
    )

    lines = [
        f"Selected pair: {selected_pair.label()}",
        f"Detected cameras: {', '.join(format_socket(socket) for socket in app.sockets)}",
        "Keys: c calibrate, d depth preview, n/p next pair, f flash, v static plot, q quit",
        "The coordinate-frame window stays visible during capture.",
    ]

    y = 130
    for line in lines:
        cv.putText(
            canvas,
            line,
            (40, y),
            cv.FONT_HERSHEY_SIMPLEX,
            0.8,
            (230, 230, 230),
            2,
            cv.LINE_AA,
        )
        y += 42

    baseline = calibration.getCameraTranslationVector(
        selected_pair.left, selected_pair.right, False
    )
    cv.rectangle(canvas, (38, 330), (1242, 520), (60, 60, 70), 2)
    dashboard_lines = [
        "Current calibration snapshot",
        f"Baseline vector: {np.asarray(baseline).ravel().tolist()}",
        f"Reference socket: {format_socket(app.sockets[0])}",
    ]
    y = 380
    for i, line in enumerate(dashboard_lines):
        cv.putText(
            canvas,
            line,
            (70, y),
            cv.FONT_HERSHEY_SIMPLEX,
            0.85 if i == 0 else 0.7,
            (200, 240, 200) if i == 0 else (220, 220, 220),
            2,
            cv.LINE_AA,
        )
        y += 44

    return canvas


def main():
    _, args = initialize_argparser()
    app = FfcCalibrationApp(args.device, fps=args.fps_limit)
    calibration = app.create_eeprom(use_device_calibration=True)
    pairs = app.get_all_stereo_pairs(calibration)
    if not pairs:
        raise RuntimeError("No stereo pairs could be derived from the connected cameras.")

    selected_pair_idx = 0
    plot_renderer = CoordinateFrameRenderer()
    dashboard_window = "calibration_dashboard"
    plot_window = "camera_frames"
    cv.namedWindow(dashboard_window, cv.WINDOW_NORMAL)
    cv.namedWindow(plot_window, cv.WINDOW_NORMAL)
    cv.resizeWindow(dashboard_window, 1280, 720)

    with app.open_device():
        while True:
            selected_pair = pairs[selected_pair_idx]
            dashboard = render_dashboard(app, calibration, selected_pair)
            plot = plot_renderer.render(
                calibration,
                app.sockets,
                reference_socket=app.sockets[0],
                selected_pair=selected_pair,
                title="Camera Coordinate Frames",
                status_lines=[
                    "OpenCV interactive mode",
                    "Press c to start calibration and keep this plot live.",
                    "Press d to inspect the current pair with stereo depth.",
                ],
            )

            cv.imshow(dashboard_window, dashboard)
            cv.imshow(plot_window, plot)

            key = cv.waitKey(1)
            if key == ord("q"):
                break
            if key == ord("n"):
                selected_pair_idx = (selected_pair_idx + 1) % len(pairs)
            elif key == ord("p"):
                selected_pair_idx = (selected_pair_idx - 1) % len(pairs)
            elif key == ord("v"):
                app.visualize_cameras(calibration, selected_pair=selected_pair)
            elif key == ord("f"):
                app.flash_calibration(calibration)
            elif key == ord("c"):
                try:
                    calibration = app.calibrate(
                        calibration,
                        status_label=f"Calibrating {selected_pair.label()}",
                    )
                    pairs = app.get_all_stereo_pairs(calibration)
                    selected_pair_idx = min(selected_pair_idx, len(pairs) - 1)
                except RuntimeError as exc:
                    print(f"Calibration aborted: {exc}")
            elif key == ord("d"):
                try:
                    app.show_depth(
                        selected_pair.left,
                        selected_pair.right,
                        calibration=calibration,
                        live_renderer=plot_renderer,
                    )
                except RuntimeError as exc:
                    print(f"Depth preview failed: {exc}")

    cv.destroyAllWindows()


if __name__ == "__main__":
    main()
