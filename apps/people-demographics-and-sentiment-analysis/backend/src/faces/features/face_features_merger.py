from typing import List, Optional
import depthai as dai
import numpy as np

from depthai_nodes import (
    Classifications,
    Predictions,
    GatheredData,
)
from messages.messages import FaceData


def merge_face_features(
    age_gender: GatheredData,
    emotions: GatheredData,
    crops: GatheredData,
    reid: GatheredData,
) -> List[FaceData]:
    """
    Matches age, gender, emotion, re-id attributes and face crops for each face detection.
    """
    reference = age_gender.reference_data
    assert isinstance(
        reference, dai.ImgDetections
    ), "Expected dai.ImgDetections, got {}".format(reference)

    detections = list(reference.detections)
    age_gender_groups = age_gender.items
    emotion_groups = emotions.items
    reid_groups = reid.items
    crop_frames = crops.items

    assert all(
        isinstance(msg, dai.NNData) for msg in reid_groups
    ), "Expected dai.NNData"

    faces: List[FaceData] = []

    for detection, age_gender_msg, emotion_msg, crop_frame, reid_msg in zip(
        detections, age_gender_groups, emotion_groups, crop_frames, reid_groups
    ):
        bbox = detection.getOuterBoundingBox()
        age_msg: Predictions = age_gender_msg["0"]
        gender_msg: Classifications = age_gender_msg["1"]

        age = int(age_msg.prediction * 100)
        gender = gender_msg.top_class
        emotion = emotion_msg.top_class

        embedding = _extract_embedding(reid_msg)
        if embedding is not None:
            embedding = _l2_normalize(embedding)

        faces.append(
            FaceData(
                bbox=bbox,
                age=age,
                gender=gender,
                emotion=emotion,
                embedding=embedding,
                crop=crop_frame,
            )
        )

    return faces


def _extract_embedding(nn_msg) -> Optional[np.ndarray]:
    embedding = nn_msg.getTensor("output", dequantize=True)
    arr = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if arr.size == 0:
        return None
    return arr


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / (n + 1e-8)
