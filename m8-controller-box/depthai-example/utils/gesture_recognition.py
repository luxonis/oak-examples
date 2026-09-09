import numpy as np
from typing import List, Tuple


def distance(a, b):
    return np.linalg.norm(a - b)


def angle(a, b, c):
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(cosine_angle)

    return np.degrees(angle)


def recognize_gesture(kpts: List[Tuple[float, float]]) -> str:
    kpts = np.array(kpts)
    d_3_5 = distance(kpts[3], kpts[5])
    d_2_3 = distance(kpts[2], kpts[3])
    angle0 = angle(kpts[0], kpts[1], kpts[2])
    angle1 = angle(kpts[1], kpts[2], kpts[3])
    angle2 = angle(kpts[2], kpts[3], kpts[4])
    thumb_state = 0
    index_state = 0
    middle_state = 0
    ring_state = 0
    little_state = 0
    gesture = None
    if angle0 + angle1 + angle2 > 460 and d_3_5 / d_2_3 > 1.2:
        thumb_state = 1
    else:
        thumb_state = 0

    if kpts[8][1] < kpts[7][1] < kpts[6][1]:
        index_state = 1
    elif kpts[6][1] < kpts[8][1]:
        index_state = 0
    else:
        index_state = -1

    if kpts[12][1] < kpts[11][1] < kpts[10][1]:
        middle_state = 1
    elif kpts[10][1] < kpts[12][1]:
        middle_state = 0
    else:
        middle_state = -1

    if kpts[16][1] < kpts[15][1] < kpts[14][1]:
        ring_state = 1
    elif kpts[14][1] < kpts[16][1]:
        ring_state = 0
    else:
        ring_state = -1

    if kpts[20][1] < kpts[19][1] < kpts[18][1]:
        little_state = 1
    elif kpts[18][1] < kpts[20][1]:
        little_state = 0
    else:
        little_state = -1

    # Gesture
    if (
        thumb_state == 1
        and index_state == 1
        and middle_state == 1
        and ring_state == 1
        and little_state == 1
    ):
        gesture = "FIVE"
    elif (
        thumb_state == 0
        and index_state == 0
        and middle_state == 0
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "FIST"
    elif (
        thumb_state == 1
        and index_state == 0
        and middle_state == 0
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "OK"
    elif (
        thumb_state == 0
        and index_state == 1
        and middle_state == 1
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "PEACE"
    elif (
        thumb_state == 0
        and index_state == 1
        and middle_state == 0
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "ONE"
    elif (
        thumb_state == 1
        and index_state == 1
        and middle_state == 0
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "TWO"
    elif (
        thumb_state == 1
        and index_state == 1
        and middle_state == 1
        and ring_state == 0
        and little_state == 0
    ):
        gesture = "THREE"
    elif (
        thumb_state == 0
        and index_state == 1
        and middle_state == 1
        and ring_state == 1
        and little_state == 1
    ):
        gesture = "FOUR"
    else:
        gesture = None

    return gesture
