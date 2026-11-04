import cv2


def reverse_resize_and_pad(padded_img, original_size, modified_size):
    """
    Reverses the resize and pad operation, scaling a processed image back to its original dimensions.

    This function reverses the ImageManip letterbox resize. It first calculates
    the padding that was added to the image and crops it. Then, it resizes the
    cropped image back to the original dimensions. This transforms annotations
    (like segmentation masks) from the processed image space back to the original
    image space.

    Args:
        padded_img (numpy.ndarray): The image that was resized and padded.
        original_size (tuple[int, int]): The original (width, height) of the image
                                         before any processing.
        modified_size (tuple[int, int]): The (width, height) of the padded image,
                                         after the ImageManip letterbox resize.

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
