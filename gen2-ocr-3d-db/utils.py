# Code taken and edited from https://github.com/MhLiao/DB

import numpy as np
import cv2
from shapely.geometry import Polygon
import pyclipper


def get_mini_boxes(contour):
    bounding_box = cv2.minAreaRect(contour)
    points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

    index_1, index_2, index_3, index_4 = 0, 1, 2, 3
    if points[1][1] > points[0][1]:
        index_1 = 0
        index_4 = 1
    else:
        index_1 = 1
        index_4 = 0
    if points[3][1] > points[2][1]:
        index_2 = 2
        index_3 = 3
    else:
        index_2 = 3
        index_3 = 2

    box = [points[index_1], points[index_2], points[index_3], points[index_4]]
    return box, min(bounding_box[1])


def box_score_fast(bitmap, _box):
    h, w = bitmap.shape[:2]
    box = _box.copy()
    xmin = np.clip(np.floor(box[:, 0].min()).astype(np.int32), 0, w - 1)
    xmax = np.clip(np.ceil(box[:, 0].max()).astype(np.int32), 0, w - 1)
    ymin = np.clip(np.floor(box[:, 1].min()).astype(np.int32), 0, h - 1)
    ymax = np.clip(np.ceil(box[:, 1].max()).astype(np.int32), 0, h - 1)

    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    box[:, 0] = box[:, 0] - xmin
    box[:, 1] = box[:, 1] - ymin
    cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
    return cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0]


def unclip(box, unclip_ratio=1.5):
    poly = Polygon(box)
    distance = poly.area * unclip_ratio / poly.length
    offset = pyclipper.PyclipperOffset()
    offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    expanded = np.array(offset.Execute(distance))
    return expanded


def get_boxes(pred, THRESH, BOX_THRESH, MIN_SIZE, MAX_CANDIDATES, UNCLIP_RATIO):
    bitmap = pred > THRESH

    height, width = pred.shape

    contours, _ = cv2.findContours(
        (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    num_contours = min(len(contours), MAX_CANDIDATES)
    boxes = np.zeros((num_contours, 4, 2), dtype=np.float32)
    scores = np.zeros((num_contours,), dtype=np.float32)

    for index in range(num_contours):
        contour = contours[index]
        points, sside = get_mini_boxes(contour)
        if sside < MIN_SIZE:
            continue
        points = np.array(points)
        score = box_score_fast(pred, points.reshape(-1, 2))
        if BOX_THRESH > score:
            continue

        box = unclip(points, UNCLIP_RATIO).reshape(-1, 1, 2)
        box, sside = get_mini_boxes(box)
        if sside < MIN_SIZE + 2:
            continue
        box = np.array(box)

        box[:, 0] = np.clip(np.round(box[:, 0]), 0, width)
        box[:, 1] = np.clip(np.round(box[:, 1]), 0, height)
        boxes[index, :, :] = box  # .astype(np.int16)
        scores[index] = score

    mask = scores > 0
    scores = scores[mask]
    boxes = boxes[mask]

    return boxes, scores


def postprocess(outputBlob):
    text = ""
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    for i in range(outputBlob.shape[0]):
        c = np.argmax(outputBlob[i][0])
        if c != 0:
            text += alphabet[c - 1]
        else:
            text += "-"

    # adjacent same letters as well as background text must be removed to get the final output
    char_list = []
    for i in range(len(text)):
        if text[i] != "-" and (not (i > 0 and text[i] == text[i - 1])):
            char_list.append(text[i])
    return "".join(char_list)
