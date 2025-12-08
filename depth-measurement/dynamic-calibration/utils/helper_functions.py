import cv2
import numpy as np


def draw_recalibration_message(image, values, angles):
    width, height = image.shape[1], image.shape[0]
    if values == []:
        lines = []
        lines.append("Data is missing please load more images with 'l'.")
        lines.append("Press any key to continue ...")
    else:
        # --- Determine message content ---
        threshold = 0.075  # degrees
        axis_names = ["Roll", "Pitch", "Yaw"]
        over_threshold = [
            i for i, angle in enumerate(np.abs(angles)) if angle > threshold
        ]

        lines = []
        lines.append("Recalibration complete")

        if over_threshold:
            axes = ", ".join([axis_names[i] for i in over_threshold])
            lines.append(f"Significant change in rotation! {axes}")
            lines.append("To permanently flash new calibration, press 's'!")
        else:
            lines.append("No significant change detected")

        lines.append(
            f"Euler angles (deg): Roll={angles[0]:.2f}, Pitch={angles[1]:.2f}, Yaw={angles[2]:.2f}"
        )
        lines.append(
            f"Depth error @1m:{values[0]:.2f}%, 2m:{values[1]:.2f}%, 5m:{values[2]:.2f}%, 10m:{values[3]:.2f}%"
        )
        lines.append("Press any key to continue ...")

    # --- Text layout parameters ---
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.2
    thickness = 2
    line_spacing = 25
    line_height = int(
        cv2.getTextSize("Test", font, font_scale, thickness)[0][1] + line_spacing
    )

    # Calculate full box height and max width
    text_sizes = [
        cv2.getTextSize(line, font, font_scale, thickness)[0] for line in lines
    ]
    box_width = max([size[0] for size in text_sizes]) + 40
    box_height = line_height * len(lines) + 20

    # Box position (centered)
    box_x = (width - box_width) // 2
    box_y = (height - box_height) // 2

    # Draw semi-transparent background box
    overlay = image.copy()
    cv2.rectangle(
        overlay, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 0, 0), -1
    )
    alpha = 0.5
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # --- Draw text lines ---
    current_y = box_y + 30
    for i, line in enumerate(lines):
        color = (255, 255, 255)
        if "Significant change" in line:
            color = (0, 0, 255)
        elif "Recalibration complete" in line:
            color = (0, 255, 0)

        text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
        text_x = box_x + (box_width - text_size[0]) // 2
        cv2.putText(
            image, line, (text_x, current_y), font, font_scale, color, thickness
        )
        current_y += line_height

    return image


def display_text(image, text):
    font_scale = 1.0
    width, height = image.shape[1], image.shape[0]
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 5)[0]
    text_width, text_height = text_size

    # Define box dimensions
    box_padding = 10
    box_width = text_width + box_padding * 2
    box_height = text_height + box_padding * 2
    box_x = (width - box_width) // 2
    box_y = (height - box_height) // 2

    # Draw semi-transparent background box
    overlay = image.copy()
    box_start = (box_x, box_y - 50)
    box_end = (box_x + box_width, box_y + box_height - 50)
    alpha = (0, 0, 0, 128)[3] / 255.0
    cv2.rectangle(overlay, box_start, box_end, (0, 0, 0, 128)[:3], -1)
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw text at the center of the box
    text_x = box_x + (box_width - text_width) // 2
    text_y = box_y + (box_height + text_height) // 2
    font_scale = 1.0
    cv2.putText(
        image,
        text,
        (text_x, text_y - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        2,
    )


def draw_health_bar(image, values, rotation, display_text=""):
    if rotation == []:
        font_scale = 1.0
        width, height = image.shape[1], image.shape[0]
        text = "Data is missing please load more images with 'l'."
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 5)[0]
        text_width, text_height = text_size

        # Define box dimensions
        box_padding = 10
        box_width = text_width + box_padding * 2
        box_height = text_height + box_padding * 2
        box_x = (width - box_width) // 2
        box_y = (height - box_height) // 2

        # Draw semi-transparent background box
        overlay = image.copy()
        box_start = (box_x, box_y - 50)
        box_end = (box_x + box_width, box_y + box_height - 50)
        alpha = (0, 0, 0, 128)[3] / 255.0
        cv2.rectangle(overlay, box_start, box_end, (0, 0, 0, 128)[:3], -1)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

        # Draw text at the center of the box
        text_x = box_x + (box_width - text_width) // 2
        text_y = box_y + (box_height + text_height) // 2
        font_scale = 1.0
        cv2.putText(
            image,
            text,
            (text_x, text_y - 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            2,
        )

    else:  # Normalize the value for display (clamp between 0 and 40)
        normalized_value = min(max(rotation), 0.2)

        # Bar parameters
        width, height = image.shape[1], image.shape[0]
        bar_width = int(width * 0.8)
        bar_height = 50
        bar_x = (width - bar_width) // 2
        bar_y = (height - bar_height) // 2  # Center the bar vertically

        # Define labels and colors
        labels = ["GOOD", "COULD BE IMPROVED", "NEEDS RECALIBRATION"]
        colors = [(0, 255, 0), (0, 255, 255), (0, 0, 255)]  # Green, Yellow, Red

        # Divide the bar into 3 equal sections
        section_width = bar_width // 3

        for i in range(3):
            start_x = bar_x + i * section_width
            end_x = start_x + section_width
            color = colors[i]

            # Draw the colored section
            cv2.rectangle(
                image, (start_x, bar_y), (end_x, bar_y + bar_height), color, -1
            )

            # Add the label inside the section
            font_scale = 0.8
            thickness = 3
            text_size = cv2.getTextSize(
                labels[i], cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )[0]
            text_x = start_x + (section_width - text_size[0]) // 2
            text_y = bar_y + (bar_height + text_size[1]) // 2
            cv2.putText(
                image,
                labels[i],
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (0, 0, 0),
                thickness,
            )

        # Map the value to the position within the bar
        if normalized_value <= 0.07:
            pointer_x = int(bar_x + (normalized_value / 0.07) * section_width)
        elif normalized_value <= 0.15:
            pointer_x = int(
                bar_x
                + section_width
                + ((normalized_value - 0.07) / 0.07) * section_width
            )
        else:
            pointer_x = int(
                bar_x
                + 2 * section_width
                + ((normalized_value - 0.15) / 0.15) * section_width
            )
        pointer_y_top = bar_y - 10
        pointer_y_bottom = bar_y + bar_height + 10
        cv2.line(
            image,
            (pointer_x, pointer_y_top),
            (pointer_x, pointer_y_bottom),
            (0, 0, 0),
            2,
        )

        # Add the numerical value above the pointer
        text = f"Depth error changes at 1m->{values[0]:.2f}%, 2m->{values[1]:.2f}%, 5m->{values[2]:.2f}%, 10m->{values[3]:.2f}%"
        font_scale = 0.9
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)[0]
        text_width, text_height = text_size

        # Define box dimensions
        box_padding = 10
        box_width = text_width + box_padding * 2
        box_height = text_height + box_padding * 2
        box_x = (width - box_width) // 2
        box_y = (height - box_height) // 2

        # Draw semi-transparent background box
        overlay = image.copy()
        box_start = (box_x, box_y + -100)
        box_end = (box_x + box_width, box_y + box_height - 100)
        alpha = (0, 0, 0, 128)[3] / 255.0
        cv2.rectangle(overlay, box_start, box_end, (0, 0, 0, 128)[:3], -1)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

        # Draw text at the center of the box
        text_x = box_x + (box_width - text_width) // 2
        text_y = box_y + (box_height + text_height) // 2
        cv2.putText(
            image,
            text,
            (text_x, text_y - 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            3,
        )
        font_scale = 1.0
        # Draw the pointer
        if display_text != "":
            text = display_text
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 5)[
                0
            ]
            text_width, text_height = text_size

            # Define box dimensions
            box_padding = 10
            box_width = text_width + box_padding * 2
            box_height = text_height + box_padding * 2
            box_x = (width - box_width) // 2
            box_y = (height - box_height) // 2

            # Draw semi-transparent background box
            overlay = image.copy()
            box_start = (box_x, box_y - 50)
            box_end = (box_x + box_width, box_y + box_height - 50)
            alpha = (0, 0, 0, 128)[3] / 255.0
            cv2.rectangle(overlay, box_start, box_end, (0, 0, 0, 128)[:3], -1)
            cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

            # Draw text at the center of the box
            text_x = box_x + (box_width - text_width) // 2
            text_y = box_y + (box_height + text_height) // 2
            font_scale = 1.0
            cv2.putText(
                image,
                text,
                (text_x, text_y - 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                2,
            )

    text = "Press any key to continue ..."
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 5)[0]
    text_width, text_height = text_size

    # Define box dimensions
    box_padding = 10
    box_width = text_width + box_padding * 2
    box_height = text_height + box_padding * 2
    box_x = (width - box_width) // 2
    box_y = (height - box_height) // 2

    # Draw semi-transparent background box
    overlay = image.copy()
    box_start = (box_x, box_y + 50)
    box_end = (box_x + box_width, box_y + box_height + 50)
    alpha = (0, 0, 0, 128)[3] / 255.0
    cv2.rectangle(overlay, box_start, box_end, (0, 0, 0, 128)[:3], -1)
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw text at the center of the box
    text_x = box_x + (box_width - text_width) // 2
    text_y = box_y + (box_height + text_height) // 2
    font_scale = 1.0
    cv2.putText(
        image,
        text,
        (text_x, text_y + 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        2,
    )
    return image


def draw_progress_bar_with_percentage(
    image,
    progress,
    coverage_check,
    bar_color=(0, 255, 0),
    bg_color=(50, 50, 50),
    thickness=50,
    bar_length_ratio=0.6,
    font_scale=1,
    font_color=(255, 255, 255),
    text_bg_color=(0, 0, 0, 128),
):
    progress = max(0, min(1, progress / 100))
    img_height, img_width = image.shape[:2]

    # Calculate bar dimensions
    bar_length = int(img_width * bar_length_ratio)
    bar_x = (img_width - bar_length) // 2
    bar_y = (img_height - thickness) // 2

    # Draw background bar
    start_point = (bar_x, bar_y)
    end_point = (bar_x + bar_length, bar_y + thickness)
    cv2.rectangle(image, start_point, end_point, bg_color, -1)

    # Draw filled bar
    filled_length = int(bar_length * progress)
    filled_end_point = (bar_x + filled_length, bar_y + thickness)
    cv2.rectangle(image, start_point, filled_end_point, bar_color, -1)

    # Draw percentage text
    percentage_text = f"{int(progress * 100)}%"
    text_size = cv2.getTextSize(
        percentage_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2
    )[0]
    text_x = bar_x + (bar_length - text_size[0]) // 2
    text_y = bar_y + (thickness + text_size[1]) // 2

    # Add semi-transparent background for percentage text
    overlay = image.copy()
    text_bg_start = (text_x - 10, text_y - text_size[1] - 10)
    text_bg_end = (text_x + text_size[0] + 10, text_y + 10)
    cv2.rectangle(overlay, text_bg_start, text_bg_end, text_bg_color[:3], -1)
    alpha = text_bg_color[3] / 255.0
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw the text
    cv2.putText(
        image,
        percentage_text,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        font_color,
        2,
    )

    # Draw "Coverage check" text below the progress bar
    if not coverage_check:
        coverage_text = "Collecting data ..."
    else:
        coverage_text = "Waiting for enough data ..."
    coverage_text_size = cv2.getTextSize(
        coverage_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2
    )[0]
    coverage_text_x = (img_width - coverage_text_size[0]) // 2
    coverage_text_y = bar_y + thickness + 20 + coverage_text_size[1]

    # Add semi-transparent background for coverage text
    overlay = image.copy()
    coverage_bg_start = (
        coverage_text_x - 10,
        coverage_text_y - coverage_text_size[1] - 10,
    )
    coverage_bg_end = (
        coverage_text_x + coverage_text_size[0] + 10,
        coverage_text_y + 10,
    )
    cv2.rectangle(overlay, coverage_bg_start, coverage_bg_end, text_bg_color[:3], -1)
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Draw the coverage check text
    cv2.putText(
        image,
        coverage_text,
        (coverage_text_x, coverage_text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        font_color,
        2,
    )

    return image


def overlay_coverage_on_gray(
    gray_image: np.ndarray, coverage_per_cell: list[list[float]], dataAquired: float
) -> np.ndarray:
    """
    Overlay green coverage map on a grayscale image.

    Args:
        gray_image: Grayscale input image (2D NumPy array).
        coverage_per_cell: 2D list of float values in range [0.0, 1.0], defining coverage per cell.

    Returns:
        Color image with green overlay per cell, proportional to coverage.
    """
    # Convert grayscale to BGR
    if len(gray_image.shape) != 3:
        color_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
    else:
        color_image = gray_image

    rows = len(coverage_per_cell)
    cols = len(coverage_per_cell[0])
    cell_width = color_image.shape[1] // cols
    cell_height = color_image.shape[0] // rows

    for y in range(rows):
        for x in range(cols):
            coverage = coverage_per_cell[y][x]
            if coverage <= 0.0:
                continue

            alpha = 0.5 * min(1.0, max(0.0, coverage))  # Clamp between 0 and 1
            green = (0, 255, 0)  # BGR

            x0 = x * cell_width
            y0 = y * cell_height
            x1 = x0 + cell_width
            y1 = y0 + cell_height

            # Overlay green box with alpha blending
            overlay = color_image.copy()
            cv2.rectangle(overlay, (x0, y0), (x1, y1), green, thickness=cv2.FILLED)
            color_image[y0:y1, x0:x1] = cv2.addWeighted(
                overlay[y0:y1, x0:x1], alpha, color_image[y0:y1, x0:x1], 1 - alpha, 0
            )
    if dataAquired != 100:
        check_coverage = False
    else:
        check_coverage = True
    draw_progress_bar_with_percentage(color_image, dataAquired, check_coverage)
    return color_image


def print_final_calibration_results(calib_quality, state: str):
    rotation_change = getattr(calib_quality, "rotationChange", [])
    depth_accuracy = getattr(calib_quality, "depthErrorDifference", [])

    print(
        f"\n<<< -----------------------------|Final Results -- {state}|------------------------------------>>>"
    )

    # Handle rotation change
    if rotation_change:
        print(
            "Rotation change[°]:",
            " ".join(f"{float(val):.3f}" for val in rotation_change),
        )
    else:
        print("Rotation change[°]: N/A")

    # Handle depth accuracy
    if depth_accuracy and len(depth_accuracy) >= 4:
        print("Improvements if new calibration is applied (as float):")
        print(
            f"1m->{depth_accuracy[0]:.2f}%, \n2m->{depth_accuracy[1]:.2f}%, \n5m->{depth_accuracy[2]:.2f}%, \n10m->{depth_accuracy[3]:.2f}%"
        )
    else:
        print("Depth accuracy data unavailable or incomplete.")

    # Instructions
    if state == "Recalibration":
        print(
            "New calibration has been applied, to apply the old one, press 'o'. To flash the new calibration, press 's'."
        )
    else:
        print("To continue with recalibration, press 'r'.")

    print(
        "<<< -----------------------------|Finished|------------------------------------>>>\n"
    )


def draw_key_commands(
    image, font_scale=1.1, color=(255, 255, 255), thickness=2, line_spacing=50
):
    """Draws key command info centered on the image with a semi-transparent full-frame background."""
    commands = [
        "DynamicCalibration mode, Key commands:",
        "[c] Calibration quality check",
        "[r] Recalibrate",
        "[a] Force calibration check",
        "[d] Force recalibrate",
        "[l] Load image",
        "[n] Apply new calibration",
        "[o] Apply old calibration",
        "[s] Flash new calibration",
        "[k] Flash old calibration",
        "[f] Flash factory calibration",
        "[x] -> Save current frames.",
        "[+/-] -> Adjust ROi size",
        "[q] Quit",
    ]

    height, width = image.shape[:2]
    overlay = image.copy()

    # Draw semi-transparent black background over the entire frame
    cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
    alpha = 0.5
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    # Calculate vertical centering
    text_block_height = line_spacing * len(commands)
    y_start = (height - text_block_height) // 2

    for i, line in enumerate(commands):
        text_size = cv2.getTextSize(
            line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )[0]
        x = (width - text_size[0]) // 2
        y = y_start + i * line_spacing
        cv2.putText(
            image,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            thickness,
            lineType=cv2.LINE_AA,
        )


def update_master_frame(
    leftFrame, rightFrame, disp_vis, fourthFrame, width=1280, height=800
):
    master_frame = np.zeros((height, width, 3), dtype=np.uint8)

    # Place subframes into master
    master_frame[0:400, 0:640] = cv2.resize(
        leftFrame, (width // 2, height // 2)
    )  # Top-left
    master_frame[0:400, 640:1280] = cv2.resize(
        rightFrame, (width // 2, height // 2)
    )  # Top-right
    master_frame[400:800, 0:640] = cv2.resize(
        disp_vis, (width // 2, height // 2)
    )  # Bottom-left
    master_frame[400:800, 640:1280] = cv2.resize(fourthFrame, (width // 2, height // 2))
    return master_frame
