import numpy as np
import cv2
from depthai_nodes import PRIMARY_COLOR, SECONDARY_COLOR

PRIMARY_COLOR_CV2 = (
    int(PRIMARY_COLOR.b * 255),
    int(PRIMARY_COLOR.g * 255),
    int(PRIMARY_COLOR.r * 255),
)
SECONDARY_COLOR_CV2 = (
    int(SECONDARY_COLOR.b * 255),
    int(SECONDARY_COLOR.g * 255),
    int(SECONDARY_COLOR.r * 255),
)


def calc_warp_corners_and_matches(
    ref_points: np.ndarray,
    dst_points: np.ndarray,
    image1: np.ndarray,
):
    H, mask = cv2.findHomography(
        ref_points,
        dst_points,
        cv2.USAC_MAGSAC,
        13.5,
        maxIters=1_000,
        confidence=0.8,
    )

    if H is None:
        return None

    mask = mask.flatten()

    h, w = image1.shape[:2]
    corners_image1 = np.array(
        [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32
    ).reshape(-1, 1, 2)

    warped_corners = cv2.perspectiveTransform(corners_image1, H)

    keypoints1 = [cv2.KeyPoint(p[0], p[1], 5) for p in ref_points]
    keypoints2 = [cv2.KeyPoint(p[0], p[1], 5) for p in dst_points]
    matches = [cv2.DMatch(i, i, 0) for i in range(len(mask)) if mask[i]]

    return warped_corners, [keypoints1, keypoints2, matches]


def xfeat_visualizer(image1, image2, features, draw_warp_corners=True):
    n = len(features)
    if n < 50:
        return image2

    ref_feats = features[0:n:2]
    tgt_feats = features[1:n:2]
    mkpts0 = np.array([[x.position.x, x.position.y] for x in ref_feats])
    mkpts1 = np.array([[x.position.x, x.position.y] for x in tgt_feats])

    result = calc_warp_corners_and_matches(
        mkpts0,
        mkpts1,
        image1,
    )

    if result is None:
        return image2

    warped_corners = result[0]
    keypoints1 = result[1][0]
    keypoints2 = result[1][1]
    matches = result[1][2]

    image2_with_corners = image2.copy()
    if draw_warp_corners:
        for i in range(len(warped_corners)):
            start_point = tuple(warped_corners[i - 1][0].astype(int))
            end_point = tuple(warped_corners[i][0].astype(int))
            cv2.line(image2_with_corners, start_point, end_point, PRIMARY_COLOR_CV2, 4)

    debug_image = cv2.drawMatches(
        image1,
        keypoints1,
        image2_with_corners,
        keypoints2,
        matches,
        None,
        matchColor=PRIMARY_COLOR_CV2,
        flags=2,
    )

    return debug_image
