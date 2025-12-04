from collections import deque
import numpy as np
import cv2
import time

import depthai as dai
from helper_functions import (
    update_master_frame,
    overlay_coverage_on_gray,
    draw_recalibration_message,
    draw_health_bar,
    display_text,
    draw_key_commands,
    print_final_calibration_results,
)


def nice_disparity_viz(in_disp_frame):
    # 1) to float, keep a valid mask
    disp = in_disp_frame.astype(np.float32)
    valid = disp > 0

    # If everything is invalid, just return a gray image
    if not np.any(valid):
        vis = np.zeros((*disp.shape, 3), np.uint8)
        vis[:] = 127
        return vis

    # 2) robust range via percentiles on valid pixels
    vals = disp[valid]
    p_low, p_high = np.percentile(vals, (2, 98))

    # Guard: widen if scene is too flat (avoid p_high == p_low)
    if p_high - p_low < 1e-6:
        p_low = float(vals.min())
        p_high = float(vals.max() + 1e-6)

    # 3) clip & normalize to 0–255
    disp_clipped = np.clip(disp, p_low, p_high)
    disp_norm = (disp_clipped - p_low) / (p_high - p_low)
    disp_u8 = np.uint8(np.clip(disp_norm * 255.0, 0, 255))

    # 4) boost mid-tones locally (CLAHE)
    #    Helps a lot when the map is mostly one color
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    disp_eq = clahe.apply(disp_u8)

    # 5) apply a perceptual colormap (TURBO if available)
    colormap = getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)
    vis = cv2.applyColorMap(disp_eq, colormap)
    return vis


# Rolling average for depth ROI means
DEPTH_HISTORY_SIZE = 10
depth_history = deque(maxlen=DEPTH_HISTORY_SIZE)
last_mouse_pos = None  # reset history if mouse moves to new pixel
mouse_coords = (-1, -1)
roi_size = 10
step_roi = 5


def on_mouse_disparity(event, x, y, flags, param):
    global mouse_coords
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_coords = (x, y)


# ---------- Pipeline definition ----------
pipeline = dai.Pipeline()

# Create camera nodes
cam_left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
cam_right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

# Request full resolution NV12 outputs
left_out = cam_left.requestFullResolutionOutput(dai.ImgFrame.Type.NV12, fps=5)
right_out = cam_right.requestFullResolutionOutput(dai.ImgFrame.Type.NV12, fps=5)
# Stereo node
stereo = pipeline.create(dai.node.StereoDepth)
stereo.setExtendedDisparity(True)
stereo.setSubpixel(True)
left_out.link(stereo.left)
right_out.link(stereo.right)

# Dynamic calibration node
dyn_calib = pipeline.create(dai.node.DynamicCalibration)
left_out.link(dyn_calib.left)
right_out.link(dyn_calib.right)


# Output queues
left_xout = stereo.syncedLeft.createOutputQueue()
right_xout = stereo.syncedRight.createOutputQueue()
disp_xout = stereo.disparity.createOutputQueue()
depth_xout = stereo.depth.createOutputQueue()

calibration_output = dyn_calib.calibrationOutput.createOutputQueue()
coverage_output = dyn_calib.coverageOutput.createOutputQueue()
quality_output = dyn_calib.qualityOutput.createOutputQueue()

command_input = dyn_calib.inputControl.createInputQueue()

device = pipeline.getDefaultDevice()
calibNew = device.readCalibration()
calibOld = device.readCalibration()
device.setCalibration(calibOld)
# ---------- Device and runtime loop ----------
pipeline.start()
start = time.time()
leftFrame = None
rightFrame = None
collectFrames = False
depthDiff = []
rotationDiff = []
displayTimer = time.time()
state = ""
print(
    "<<< -----------------------------|Introduction|------------------------------->>>"
)
print("Key commands:")
print("[c] -> Calibration quality check")
print("[r] -> Recalibrate")
print("[a] -> Force calibration check")
print("[d] -> Force recalibrate")
print("[l] Load image")
print("[n] -> Apply new calibration")
print("[o] -> Apply old calibration")
print("[s] -> Flash new calibration")
print("[k] -> Flash old calibration")
print("[f] -> Flash factory calibration")
print("[x] -> Save current frames.")
print("[q] -> Quit")
print(
    "<<< -----------------------------|Start the pipeline!|------------------------->>>"
)
cv2.namedWindow("MasterFrame", cv2.WINDOW_NORMAL)
window_size = [1920, 1200]
cv2.resizeWindow("MasterFrame", window_size[0], window_size[1])
cv2.setMouseCallback("MasterFrame", on_mouse_disparity)
text = ""
overall_coverage = None
overall_dataAcquired = 0
with pipeline:
    max_disp = stereo.initialConfig.getMaxDisparity()
    while True:
        now = time.time()
        in_left = left_xout.get()
        in_right = right_xout.get()
        in_disp = disp_xout.get()
        in_depth = depth_xout.get()
        running_calibration = device.getCalibration()
        M = np.array(
            running_calibration.getCameraIntrinsics(dai.CameraBoardSocket.CAM_B)
        )
        coverage = coverage_output.tryGet()
        calibration_result = calibration_output.tryGet()

        fourthFrame = np.zeros((800, 1280, 3), dtype=np.uint8)
        if in_disp:
            assert isinstance(in_disp, dai.ImgFrame)
            disp_frame = in_disp.getFrame()
            disp_vis = nice_disparity_viz(disp_frame)

        if in_depth:
            assert isinstance(in_depth, dai.ImgFrame)
            depth_frame = in_depth.getFrame()

        if in_left:
            assert isinstance(in_left, dai.ImgFrame)
            leftFrame = in_left.getCvFrame()

        if in_right:
            assert isinstance(in_right, dai.ImgFrame)
            rightFrame = in_right.getCvFrame()

        if calibration_result:
            print(f"Intermediate Information: {calibration_result.info}")

        if calibration_result and calibration_result.calibrationData:
            state = "Recalibration"
            finalDisplay = True
            rotationDiff = np.array(
                getattr(
                    calibration_result.calibrationData.calibrationDifference,
                    "rotationChange",
                    [],
                ).copy()
            )
            depthDiff = getattr(
                calibration_result.calibrationData.calibrationDifference,
                "depthErrorDifference",
                [],
            ).copy()
            new_calibration = calibration_result.calibrationData.newCalibration
            calibNew = new_calibration
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                        new_calibration
                    )
                )
            )
            print("Applying new calibration.")

        if coverage:
            overall_coverage = coverage.coveragePerCellA
            overall_dataAcquired = coverage.dataAcquired

        masterFrame = update_master_frame(leftFrame, rightFrame, disp_vis, fourthFrame)

        if state == "CollectFrames" and overall_coverage is not None:
            leftFrame = overlay_coverage_on_gray(
                leftFrame, overall_coverage, overall_dataAcquired
            )
            rightFrame = overlay_coverage_on_gray(
                rightFrame, overall_coverage, overall_dataAcquired
            )
            masterFrame = update_master_frame(
                leftFrame, rightFrame, disp_vis, fourthFrame
            )

        elif state == "Recalibration" and finalDisplay:
            leftFrame = draw_recalibration_message(leftFrame, depthDiff, rotationDiff)
            rightFrame = draw_recalibration_message(rightFrame, depthDiff, rotationDiff)
            fourthFrame = draw_recalibration_message(
                fourthFrame, depthDiff, rotationDiff
            )
            masterFrame = update_master_frame(
                leftFrame, rightFrame, disp_vis, fourthFrame
            )
            overall_coverage = None  # Reset coverage after recalibration
            overall_dataAcquired = 0
            key_end = cv2.waitKey(1)
            if key_end != -1:  # -1 means no key was pressed
                finalDisplay = False

        elif state == "Calibration check" and finalDisplay:
            fourthFrame = draw_health_bar(
                fourthFrame,
                depthDiff,
                rotationDiff,
                display_text=f"{text} Health Bad of Depth Difference Error",
            )
            masterFrame = update_master_frame(
                leftFrame, rightFrame, disp_vis, fourthFrame
            )
            key_end = cv2.waitKey(1)
            if key_end != -1:  # -1 means no key was pressed
                finalDisplay = False

        elif state == "Display Text" and finalDisplay:
            display_text(masterFrame, text)
            if np.abs(start_time - now) > 2:
                finalDisplay = False
        else:
            draw_key_commands(fourthFrame)
            masterFrame = update_master_frame(
                leftFrame, rightFrame, disp_vis, fourthFrame
            )

        disp_x_start, disp_y_start = 0, masterFrame.shape[0] // 2
        disp_x_end, disp_y_end = masterFrame.shape[1] // 2, window_size[0] // 2
        scale_x = masterFrame.shape[1] / window_size[0]
        scale_y = masterFrame.shape[0] / window_size[1]
        scaled_mouse_x = int(mouse_coords[0] * scale_x)
        scaled_mouse_y = int(mouse_coords[1] * scale_y)
        if (
            disp_x_start <= scaled_mouse_x < disp_x_end
            and disp_y_start <= scaled_mouse_y < disp_y_end
            and in_disp
        ):
            local_x = scaled_mouse_x  # disp_vis x offset
            local_y = scaled_mouse_y - masterFrame.shape[0] // 2  # disp_vis y offset
            if (
                0 <= local_x < depth_frame.shape[1]
                and 0 <= local_y < depth_frame.shape[0]
            ):
                cy = int(round(local_y * 2))
                cx = int(round(local_x * 2))
                half = roi_size
                y0 = max(0, cy - half)
                y1 = min(depth_frame.shape[0], cy + half + 1)
                x0 = max(0, cx - half)
                x1 = min(depth_frame.shape[1], cx + half + 1)

                roi = depth_frame[y0:y1, x0:x1].astype(np.float32)

                # Rolling-mean over last 10 frames; clears if cursor center changes
                cur_mouse_pos = (cx, cy)
                if last_mouse_pos != cur_mouse_pos:
                    depth_history.clear()
                    last_mouse_pos = cur_mouse_pos

                valid = roi > 0
                if np.any(valid):
                    depth_mm = float(roi[valid].mean())  # in millimeters
                    depth_history.append(depth_mm)
                # else: keep previous history if current ROI is invalid

                if len(depth_history) > 0:
                    depth_val = float(np.mean(depth_history)) / 1000.0  # mm -> m
                else:
                    depth_val = float("nan")

                # === Compute Euclidean distance using intrinsics ===
                # Intrinsic matrix parameters (from M)
                fx = M[0, 0]
                fy = M[1, 1]
                cx_intr = M[0, 2]
                cy_intr = M[1, 2]

                # Compute normalized pixel coordinates (optical center offset)
                X = (cx - cx_intr) * depth_val / fx
                Y = (cy - cy_intr) * depth_val / fy
                Z = depth_val

                euclidean_dist = float(np.sqrt(X**2 + Y**2 + Z**2))  # meters
                # === Display text in two lines ===
                text_pos_1 = (scaled_mouse_x + 10, scaled_mouse_y + 10)
                text_pos_2 = (scaled_mouse_x + 10, scaled_mouse_y + 30)

                display_text_depth = f"Depth: {depth_val:.2f} m"
                display_text_euc = f"3D Dist: {euclidean_dist:.2f} m"

                # Example of drawing (depends on your OpenCV overlay logic):
                cv2.putText(
                    masterFrame,
                    display_text_depth,
                    text_pos_1,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    masterFrame,
                    display_text_euc,
                    text_pos_2,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    1,
                    cv2.LINE_AA,
                )

                # ROI display area (unchanged)
                disp_x0 = disp_x_start + (x0 // 2)
                disp_x1 = disp_x_start + ((x1 - 1) // 2 + 1)
                disp_y0 = disp_y_start + (y0 // 2)
                disp_y1 = disp_y_start + ((y1 - 1) // 2 + 1)

                overlay = masterFrame.copy()
                cv2.rectangle(
                    overlay, (disp_x0, disp_y0), (disp_x1, disp_y1), (0, 0, 255), -1
                )
                alpha = 0.6
                masterFrame = cv2.addWeighted(
                    overlay, alpha, masterFrame, 1 - alpha, 0, masterFrame
                )

        if leftFrame is not None and rightFrame is not None:
            cv2.imshow("MasterFrame", cv2.resize(masterFrame, (1920, 1200)))

        key = cv2.waitKey(1)

        if key == ord("q"):
            cv2.destroyAllWindows()
            exit()
            break

        if key == ord("c"):
            depthDiff = []
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.LoadImage()
                )
            )
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.CalibrationQuality(True)
                )
            )
            quality = quality_output.get()
            state = "Calibration check"
            finalDisplay = True
            depthDiff = getattr(quality.qualityData, "depthErrorDifference", []).copy()
            rotationDiff = getattr(quality.qualityData, "rotationChange", []).copy()
            print_final_calibration_results(quality.qualityData, state)
            print("Sending command for calibQualityCheck")

        elif key == ord("r"):
            depthDiff = []
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.StartCalibration()
                )
            )
            state = "CollectFrames"
            print("Sending command for recalibration")

        elif key == ord("a"):
            depthDiff = []
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.LoadImage()
                )
            )
            coverage = coverage_output.tryGet()
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.CalibrationQuality(True)
                )
            )
            quality = quality_output.get()
            state = "Calibration check"
            depthDiff = getattr(quality.qualityData, "depthErrorDifference", []).copy()
            rotationDiff = getattr(quality.qualityData, "rotationChange", []).copy()
            finalDisplay = True
            print_final_calibration_results(quality.qualityData, state)
            print("Sending command for forced calibQualityCheck")

        elif key == ord("d"):
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.Calibrate(True)
                )
            )
            state = "Recalibration"
            finalDisplay = True
            print("Sending command for forced recalibration.")

        elif key == ord("n"):
            state = "Display Text"
            text = "New calibration applied successfully."
            finalDisplay = True
            print("Device applying new calibration")
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.ApplyCalibration(calibNew)
                )
            )
            print("New calibration applied successfully.")
            start_time = time.time()

        elif key == ord("o"):
            state = "Display Text"
            text = "Old calibration applied successfully."
            finalDisplay = True
            print("Device applying old calibration")
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.ApplyCalibration(calibOld)
                )
            )
            print("Old calibration applied successfully.")
            start_time = time.time()

        elif key == ord("s"):
            state = "Display Text"
            text = "New calibration flashed successfully."
            finalDisplay = True
            print("Device flasing new calibration")
            device.flashCalibration(calibNew)
            print("New calibration flashed successfully.")
            start_time = time.time()

        elif key == ord("k"):
            state = "Display Text"
            text = "Old calibration flashed successfully."
            finalDisplay = True
            print("Device flasing old calibration")
            device.flashCalibration(calibOld)
            print("Old calibration flashed successfully.")
            start_time = time.time()
        elif key == ord("f"):
            state = "Display Text"
            text = "Factory calibration flashed successfully."
            finalDisplay = True
            print("Device flashing factory calibration")
            device.flashCalibration(device.readFactoryCalibration())
            print("Factory calibration flashed successfully.")
            start_time = time.time()
        elif key == ord("l"):
            state = "Display Text"
            text = "Image loaded successfully."
            finalDisplay = True
            print("Loading image ... ")
            command_input.send(
                dai.DynamicCalibrationControl(
                    dai.DynamicCalibrationControl.Commands.LoadImage()
                )
            )
            print("Image loaded successfully.")
            start_time = time.time()

        elif key == ord("+"):
            state = "Display Text"
            text = f"Increase ROI size by 1. \nCurrent size {roi_size // 2}x {roi_size // 2}"
            finalDisplay = True
            if roi_size > step_roi:
                roi_size += step_roi
            else:
                roi_size += step_roi
            start_time = time.time()

        elif key == ord("-"):
            state = "Display Text"
            text = f"Decrease ROI size by 1. \nCurrent size {roi_size // 2}x {roi_size // 2}"
            finalDisplay = True
            if roi_size > step_roi:
                roi_size -= step_roi
            else:
                roi_size = step_roi
            start_time = time.time()

        elif key == ord("x"):
            state = "Display Text"
            text = "Saved current frames to img_left_*.npy and img_right_*.npy"
            finalDisplay = True
            print("Saved current frames to img_left_*.npy and img_right_*.npy.")
            import os

            path = os.path.dirname(os.path.abspath(__file__))
            folder = os.path.join(path, f"dynamic_calib_dataset_{device.getMxId()}/")
            import json

            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            i = time.time() - start
            with open(f"{folder}calibration_before.json", "w") as f:
                json.dump(device.readCalibration().eepromToJson(), f, indent=4)
            print("Saved current calibration to calibration_before.json")
            np.save(f"{folder}img_left_{i}.npy", leftFrame)
            np.save(f"{folder}img_right_{i}.npy", rightFrame)
            print("Saved current frames to img_left_*.npy and img_right_*.npy")

            calibFactory = device.readFactoryCalibration()
            device.readCalibration().eepromToJsonFile(f"{folder}calibration.json")
            calibFactory.eepromToJsonFile(f"{folder}factoryCalibration.json")
            start_time = time.time()

            print("Finished saving dataset.")
    pipeline.stop()
