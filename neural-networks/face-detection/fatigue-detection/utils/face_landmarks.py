from typing import Tuple
import cv2
import math
import numpy as np
from depthai_nodes import Keypoints


def determine_fatigue(
    shape: Tuple[int, int], face_keypoints: Keypoints, pitch_angle: int = 20
):
    h, w = shape  # frame.shape[:2]
    face_points_2d = np.array(
        [[int(kp.x * w), int(kp.y * h)] for kp in face_keypoints.keypoints]
    )

    left_eye_idx = [33, 160, 158, 133, 144, 153]
    right_eye_idx = [263, 387, 385, 362, 373, 380]

    left_eye = face_points_2d[left_eye_idx]
    right_eye = face_points_2d[right_eye_idx]

    pose_indices = [199, 4, 33, 263, 61, 291]
    image_points = face_points_2d[pose_indices].astype("double")

    success, rotation_vector, translation_vector, camera_matrix, dist_coeffs = (
        get_pose_estimation(shape, image_points)
    )

    head_tilted = False
    if success:
        pitch, yaw, roll = get_euler_angles(rotation_vector)
        if pitch < -pitch_angle:
            head_tilted = True

    left_ear = calc_eye_aspect_ratio(left_eye)
    right_ear = calc_eye_aspect_ratio(right_eye)
    ear = (left_ear + right_ear) / 2.0
    eyes_closed = True if ear < 0.15 else False

    return head_tilted, eyes_closed


def calc_eye_aspect_ratio(eye_points):
    A = np.linalg.norm(eye_points[1] - eye_points[4])
    B = np.linalg.norm(eye_points[2] - eye_points[5])
    C = np.linalg.norm(eye_points[0] - eye_points[3])
    return (A + B) / (2.0 * C)


def get_pose_estimation(shape, image_points):
    # 3D model points corresponding to the landmarks above.
    model_points = np.array(
        [
            (0.0, -7.9422, 5.1812),  # Chin
            (0.0, -0.4632, 7.5866),  # Nose tip
            (-4.4459, 2.6640, 3.1734),  # Left eye corner
            (4.4459, 2.6640, 3.1734),  # Right eye corner
            (-2.4562, -4.3426, 4.2839),  # Left mouth corner
            (2.4562, -4.3426, 4.2839),  # Right mouth corner
        ],
        dtype="double",
    )

    focal_length = shape[1]
    center = (shape[1] / 2, shape[0] / 2)
    camera_matrix = np.array(
        [[focal_length, 0, center[0]], [0, focal_length, center[1]], [0, 0, 1]],
        dtype="double",
    )

    # Assuming no lens distortion
    dist_coeffs = np.zeros((4, 1))

    # Solve for pose
    success, rotation_vector, translation_vector = cv2.solvePnP(
        model_points,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    return success, rotation_vector, translation_vector, camera_matrix, dist_coeffs


def get_euler_angles(rotation_vector):
    # Convert rotation vector to rotation matrix
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

    # Compute Euler angles from the rotation matrix.
    sy = math.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)

    singular = sy < 1e-6
    if not singular:
        pitch = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        # Fallback for singular case
        pitch = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = 0

    # Convert radians to degrees
    pitch_deg = pitch * 180 / math.pi
    yaw_deg = yaw * 180 / math.pi
    roll_deg = roll * 180 / math.pi

    return pitch_deg, yaw_deg, roll_deg
