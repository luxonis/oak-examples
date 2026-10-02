import cv2
import depthai as dai
import numpy as np


def read_intrinsics(device: dai.Device, resize_w: int, resize_h: int) -> tuple:
    """Reads the camera intrinsics from the device and returns the focal lengths and principal points."""
    calibData = device.readCalibration2()
    M2 = np.array(
        calibData.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, resize_w, resize_h)
    )  # Because the displayed image is with NN input res
    fx = M2[0, 0]
    fy = M2[1, 1]
    cx = M2[0, 2]
    cy = M2[1, 2]
    return fx, fy, cx, cy


def resize_and_pad(img, target_size, pad_color=0):
    """
    Resizes an image to a target size while maintaining its aspect ratio by adding padding.

    This function first calculates the new dimensions of the image that fit within the
    target size while preserving the original aspect ratio. It then resizes the image
    to these new dimensions and adds padding to the remaining space to meet the
    target size.

    Args:
        img (numpy.ndarray): The input image as a NumPy array.
        target_size (tuple[int, int]): A tuple (width, height) representing the
                                       target dimensions for the output image.
        pad_color (int, optional): The grayscale value used for padding. Defaults to 0 (black).

    Returns:
        numpy.ndarray: The resized and padded image as a NumPy array.
    """
    # Compute the aspect ratio of the original and target image
    original_aspect = img.shape[1] / img.shape[0]
    target_aspect = target_size[0] / target_size[1]

    if original_aspect > target_aspect:
        # Original has a wider aspect than target. Resize based on width.
        new_w = target_size[0]
        new_h = int(new_w / original_aspect)
    else:
        # Original has a taller aspect or equal to target. Resize based on height.
        new_h = target_size[1]
        new_w = int(new_h * original_aspect)

    # Resize the image
    img_resized = cv2.resize(img, (new_w, new_h))

    # Compute the padding required
    pad_vert = target_size[1] - new_h
    pad_horz = target_size[0] - new_w

    pad_top = pad_vert // 2
    pad_bottom = pad_vert - pad_top
    pad_left = pad_horz // 2
    pad_right = pad_horz - pad_left

    # Pad the image
    img_padded = cv2.copyMakeBorder(
        img_resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_CONSTANT,
        value=pad_color,
    )

    return img_padded


def reverse_resize_and_pad(padded_img, original_size, modified_size):
    """
    Reverses the resize and pad operation, scaling a processed image back to its original dimensions.

    This function is the inverse of `resize_and_pad`. It first calculates the padding
    that was added to the image and crops it. Then, it resizes the cropped image
    back to the original dimensions. This is useful for transforming annotations
    (like segmentation masks) from the processed image space back to the
    original image space.

    Args:
        padded_img (numpy.ndarray): The image that was resized and padded.
        original_size (tuple[int, int]): The original (width, height) of the image
                                         before any processing.
        modified_size (tuple[int, int]): The (width, height) of the padded image,
                                         which is the result of the `resize_and_pad` function.

    Returns:
        numpy.ndarray: The image resized back to its original dimensions.
    """
    original_width, original_height = original_size
    modified_width, modified_height = modified_size

    # Compute the aspect ratio of the original and target image
    original_aspect = original_width / original_height
    modified_aspect = modified_width / modified_height

    if original_aspect > modified_aspect:
        # Original has a wider aspect than target. Resize based on width.
        new_w = modified_width
        new_h = int(new_w / original_aspect)
    else:
        # Original has a taller aspect or equal to target. Resize based on height.
        new_h = modified_height
        new_w = int(new_h * original_aspect)

    # Compute padding
    pad_vert = modified_height - new_h
    pad_horz = modified_width - new_w

    pad_top = pad_vert // 2
    pad_bottom = pad_vert - pad_top
    pad_left = pad_horz // 2
    pad_right = pad_horz - pad_left

    # Remove padding by cropping
    cropped_img = padded_img[
        pad_top : modified_height - pad_bottom, pad_left : modified_width - pad_right
    ]

    # Resize back to original dimensions
    original_img = cv2.resize(cropped_img, (original_width, original_height))

    return original_img
