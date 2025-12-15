from enum import Enum


class ConditionKey(str, Enum):
    TIMED = "timed"
    NO_DETECTIONS = "noDetections"
    LOW_CONFIDENCE = "lowConfidence"
    LOST_MID = "lostMid"
