import cv2
import time
import base64
import numpy as np
import depthai as dai
from typing import Dict, List, Optional, Set

from messages.messages import PeopleMessage, PersonData, FaceData
from .statistics.aggregated_stats import StatsAggregator

MAX_PEOPLE_SLOTS = 3
KEEP_PEOPLE = 10
ID_DECIDED = {"NEW", "REID"}
PLACEHOLDER_URL = "placeholders/empty.jpg"


class MonitorFacesNode(dai.node.HostNode):
    """
    Collects face metadata and maintains recency-ordered set of people for FE display.
    Emits a payload with person statistics and per-slot face info.
    """

    def __init__(self, max_people_slots: int = MAX_PEOPLE_SLOTS) -> None:
        super().__init__()

        # Latest PersonData per person_id
        self.people: Dict[str, PersonData] = {}
        self.people_last_seen: Dict[str, float] = {}

        # Image cache: Maps person_id -> base64 string
        self._face_img_cache: Dict[str, str] = {}

        # Face slots management
        self.max_people_slots = max_people_slots
        self.people_slots: List[Optional[str]] = [None] * self.max_people_slots

        # Emit payload at ~1 Hz
        self._last_emit_ts = 0.0
        self._emit_interval = 1.0
        self._emit_seq = 0
        self.latest_payload: Optional[dict] = None

        # Person IDs observed in the most recent frame
        self._ids_seen_in_current_frame: Set[str] = set()

        self.stats = StatsAggregator(maxlen=2000)

    def build(self, people: dai.Node.Output) -> "MonitorFacesNode":
        self.link_args(people)
        return self

    def process(self, people_msg: dai.Buffer) -> None:
        assert isinstance(people_msg, PeopleMessage)

        people: List[PersonData] = people_msg.people
        now = time.monotonic()

        self._ids_seen_in_current_frame = set()

        for person in people:
            if person.reid_status not in ID_DECIDED or not person.re_id:
                continue

            face: Optional[FaceData] = person.face
            if not face or face.age is None or not face.gender or not face.emotion:
                continue

            person_id = person.re_id
            self._ids_seen_in_current_frame.add(person_id)

            # Update data
            is_new_person = person_id not in self.people
            self.people[person_id] = person
            self.people_last_seen[person_id] = now

            self.stats.add(
                age=int(face.age),
                gender=face.gender,
                emotion=face.emotion,
            )

            # Manage face display slots
            if is_new_person or (person_id not in self.people_slots):
                self.move_face_to_front(person_id)

        # ---- 1 Hz payload emission ----
        if (now - self._last_emit_ts) >= self._emit_interval:
            self._emit_seq += 1
            self._last_emit_ts = now
            self.trim_people(n_keep=KEEP_PEOPLE)
            self.latest_payload = self._build_payload(timestamp=now)

    # ---------- payload builder ----------

    def _build_payload(self, timestamp: float) -> dict:
        faces_by_slot: List[dict] = []

        for person_id in self.people_slots:
            url = self.placeholder_url()
            payload = {"img_url": url}

            if person_id and person_id in self.people:
                person = self.people[person_id]
                face = person.face

                if face:
                    # Only re-encdoe crop if face is live
                    url = self._face_img_cache.get(person_id)

                    if (person_id in self._ids_seen_in_current_frame) or (url is None):
                        crop = face.crop
                        if crop is not None:
                            bgr = crop.getCvFrame()
                            if bgr is not None and bgr.size > 0:
                                img_b64 = self.encode_bgr_to_base64(bgr)
                                url = f"data:image/jpeg;base64,{img_b64}"
                                self._face_img_cache[person_id] = url

                    if url:
                        payload = {
                            "id": person_id,
                            "status": person.reid_status or "",
                            "age": int(face.age),
                            "gender": face.gender,
                            "emotion": face.emotion,
                            "img_url": url,
                        }

            faces_by_slot.append(payload)

        return {
            "seq": self._emit_seq,
            "timestamp": timestamp,
            "faces": faces_by_slot,
            "stats": self.stats.get_stats(),
        }

    # ---------- helpers ----------

    def move_face_to_front(self, person_id: str) -> None:
        """
        Moves the specified person to the first slot for UI priority.
        Maintains the sliding window of displayed faces.
        """
        self.people_slots = [pid for pid in self.people_slots if pid != person_id]
        self.people_slots.insert(0, person_id)
        self._pad_slots()

    def _pad_slots(self) -> None:
        if len(self.people_slots) < self.max_people_slots:
            self.people_slots += [None] * (
                self.max_people_slots - len(self.people_slots)
            )
        elif len(self.people_slots) > self.max_people_slots:
            self.people_slots = self.people_slots[: self.max_people_slots]

    def trim_people(self, n_keep: int) -> None:
        """
        Keep only the 'n_keep' most recently seen person_ids.
        """
        if len(self.people) <= n_keep:
            return

        recent_ids = sorted(
            self.people_last_seen,
            key=self.people_last_seen.get,
            reverse=True,
        )[:n_keep]
        keep_ids = set(recent_ids)

        self.people = {person_id: self.people[person_id] for person_id in keep_ids}
        self.people_last_seen = {
            person_id: self.people_last_seen[person_id] for person_id in keep_ids
        }

        # Drop cached images for evicted IDs
        self._face_img_cache = {
            person_id: self._face_img_cache[person_id]
            for person_id in keep_ids
            if person_id in self._face_img_cache
        }

        # Clean up slots
        self.people_slots = [
            person_id if person_id in keep_ids else None
            for person_id in self.people_slots
        ]
        self._pad_slots()

    def encode_bgr_to_base64(self, bgr: np.ndarray) -> str:
        _, jpeg = cv2.imencode(".jpg", bgr)
        return base64.b64encode(jpeg.tobytes()).decode("utf-8")

    def placeholder_url(self) -> str:
        return f"{PLACEHOLDER_URL}?t={self._emit_seq}"

    def visualizer_get_payload(self, _=None) -> dict:
        """
        Returns latest face detections and statistics to the frontend.
        """
        if not self.latest_payload:
            return {
                "faces": [],
                "stats": self.stats.empty_stats(),
            }
        return self.latest_payload
