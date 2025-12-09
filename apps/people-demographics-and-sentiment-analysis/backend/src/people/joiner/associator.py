from dataclasses import dataclass
from typing import Optional, List, Tuple
import depthai as dai

from messages.messages import FaceData


@dataclass
class PersonCandidate:
    tracklet_id: int
    bbox: Tuple[float, float, float, float]
    tracking_status: str
    face: Optional[FaceData]


class PersonFaceAssociator:
    """
    Computes best face-tracklet assignment using bbox overlap.
    """

    def __init__(self, min_overlap_ratio: float = 0.6):
        self._min_overlap_ratio = min_overlap_ratio

    def match(
        self, faces: List[FaceData], tracklets: List[dai.Tracklet]
    ) -> List[PersonCandidate]:
        candidates: List[PersonCandidate] = []

        for tracklet in tracklets:
            candidates.append(
                PersonCandidate(
                    tracklet_id=tracklet.id,
                    bbox=self._tracklet_to_bbox(tracklet),
                    tracking_status=tracklet.status.name,
                    face=None,
                )
            )

        for face in faces:
            idx, ratio = self._best_person_for_face(face.bbox, tracklets)
            if idx is None or ratio < self._min_overlap_ratio:
                continue
            candidates[idx].face = face

        return candidates

    def _best_person_for_face(
        self, face_box: Tuple[float, float, float, float], people: List[dai.Tracklet]
    ) -> Tuple[Optional[int], float]:
        best_idx, best_overlap = None, 0.0
        for i, tracklet in enumerate(people):
            person_box = self._tracklet_to_bbox(tracklet)
            overlap = self.bboxes_overlap_area(person_box, face_box)
            if overlap > best_overlap:
                best_overlap, best_idx = overlap, i

        face_area = self.bbox_area(face_box)
        ratio = best_overlap / face_area if face_area > 0 else 0.0
        return best_idx, ratio

    @staticmethod
    def _tracklet_to_bbox(tracklet: dai.Tracklet) -> Tuple[float, float, float, float]:
        roi = tracklet.roi
        return (
            roi.topLeft().x,
            roi.topLeft().y,
            roi.bottomRight().x,
            roi.bottomRight().y,
        )

    @staticmethod
    def bbox_area(box: Tuple):
        x1, y1, x2, y2 = box
        return max(0, x2 - x1) * max(0, y2 - y1)

    @staticmethod
    def bboxes_overlap_area(a: Tuple, b: Tuple):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        x1, y1 = max(ax1, bx1), max(ay1, by1)
        x2, y2 = min(ax2, bx2), min(ay2, by2)
        if x2 > x1 and y2 > y1:
            return (x2 - x1) * (y2 - y1)
        return 0
