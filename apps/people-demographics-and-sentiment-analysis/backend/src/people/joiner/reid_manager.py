# core/reid/reid_manager.py
from dataclasses import dataclass
from collections import deque
from typing import Dict, Optional, Set, List
import numpy as np
import time

REID_MATCH_THRESHOLD = 0.4

HIGH_LEARNING_THRESHOLD = 0.4
MID_LEARNING_THRESHOLD = 0.35

LEARNING_RATE = 0.05
MID_LEARNING_RATE = 0.01

K_SAMPLES_BEFORE_DECISION = 5


@dataclass
class TrackState:
    embeddings: deque
    state: str  # "TBD" | "NEW" | "REID"
    rid: Optional[str]
    decided: bool


@dataclass
class MemoryEntry:
    embeddings_mean: np.ndarray  # normalized mean embedding
    last_seen: float


class ReIdManager:
    """
    Maintains per-tracklet re-identification state and a global per-person embedding memory.
    """

    def __init__(
        self, k_face_samples: int = K_SAMPLES_BEFORE_DECISION, max_memory: int = 100
    ):
        self._k_face_samples = k_face_samples
        self._max_memory = max_memory

        self._tracklet_reid_states: Dict[int, TrackState] = {}
        self._memory: Dict[str, MemoryEntry] = {}
        self._next_reid = 0

    def cleanup(self, live_tracklet_ids: Set[int]) -> None:
        """Removes state for people who left the camera view."""
        self._tracklet_reid_states = {
            tracklet_id: state
            for tracklet_id, state in self._tracklet_reid_states.items()
            if tracklet_id in live_tracklet_ids
        }

    def update(
        self, tracklet_id: int, embedding: Optional[np.ndarray]
    ) -> tuple[Optional[str], str]:
        """
        Update ReID state for a given tracklet with a new embedding.
        Note: 'embedding' is expected to be already L2-normalized.
        """
        tracklet_state = self._get_or_create_state(tracklet_id)

        if embedding is None:
            return tracklet_state.rid, tracklet_state.state

        # Already decided for this tracklet
        if tracklet_state.decided and tracklet_state.rid:
            self._active_learning(tracklet_state.rid, embedding)
            return tracklet_state.rid, tracklet_state.state

        # Still gathering samples for this tracklet
        tracklet_state.embeddings.append(embedding)
        if len(tracklet_state.embeddings) < self._k_face_samples:
            return tracklet_state.rid, tracklet_state.state

        # Decide identity
        embeddings_mean = self._embeddings_mean(list(tracklet_state.embeddings))
        match_rid = self._find_best_match(embeddings_mean)

        if match_rid:
            tracklet_state.rid = match_rid
            tracklet_state.state = "REID"
            self._active_learning(match_rid, embeddings_mean, matched=True)
        else:
            tracklet_state.rid = self._create_new_identity(embeddings_mean)
            tracklet_state.state = "NEW"

        tracklet_state.decided = True
        tracklet_state.embeddings.clear()

        return tracklet_state.rid, tracklet_state.state

    # --- Core Logic ---

    def _get_or_create_state(self, tracklet_id: int) -> TrackState:
        if tracklet_id not in self._tracklet_reid_states:
            self._tracklet_reid_states[tracklet_id] = TrackState(
                embeddings=deque(maxlen=self._k_face_samples),
                state="TBD",
                rid=None,
                decided=False,
            )
        return self._tracklet_reid_states[tracklet_id]

    def _active_learning(
        self, rid: str, new_embedding: np.ndarray, matched: bool = False
    ) -> None:
        """
        Refine the stored embedding for a known RID using EMA.

        If 'matched' is True, update regardless of similarity (used on first REID decision).
        Otherwise, update only when similarity exceeds learning threshold, with specified learning rate.
        """
        entry = self._memory.get(rid)
        if not entry:
            return

        entry.last_seen = time.time()

        if matched:
            self._refine_embedding(
                entry=entry, new_embedding=new_embedding, lr=LEARNING_RATE
            )
            return

        similarity = self._cos_similarity(entry.embeddings_mean, new_embedding)
        if similarity >= HIGH_LEARNING_THRESHOLD:
            # Strong update
            self._refine_embedding(
                entry=entry, new_embedding=new_embedding, lr=LEARNING_RATE
            )
        elif similarity >= MID_LEARNING_THRESHOLD:
            # Softer update
            self._refine_embedding(
                entry=entry, new_embedding=new_embedding, lr=MID_LEARNING_RATE
            )

    def _refine_embedding(
        self, entry: MemoryEntry, new_embedding: np.ndarray, lr: float
    ) -> None:
        # EMA update
        updated = (entry.embeddings_mean * (1 - lr)) + (new_embedding * lr)
        entry.embeddings_mean = self._norm(updated)

    def _find_best_match(self, embeddings_mean: np.ndarray) -> Optional[str]:
        """
        Find the best matching RID in memory based on cosine similarity.
        """
        if not self._memory:
            return None

        best_rid = None
        best_score = -1.0

        for rid, entry in self._memory.items():
            score = self._cos_similarity(embeddings_mean, entry.embeddings_mean)

            if score > best_score:
                best_score = score
                best_rid = rid

        if best_score >= REID_MATCH_THRESHOLD:
            return best_rid
        return None

    def _create_new_identity(self, embeddings_mean: np.ndarray) -> str:
        rid = str(self._next_reid)
        self._next_reid += 1
        self._memory[rid] = MemoryEntry(
            embeddings_mean=embeddings_mean, last_seen=time.time()
        )
        self._trim_memory()
        return rid

    def _trim_memory(self) -> None:
        if len(self._memory) <= self._max_memory:
            return
        sorted_items = sorted(
            self._memory.items(), key=lambda kv: kv[1].last_seen, reverse=True
        )
        self._memory = dict(sorted_items[: self._max_memory])

    # --- internal helpers ---
    @staticmethod
    def _embeddings_mean(embeddings: List[np.ndarray]) -> np.ndarray:
        return ReIdManager._norm(np.mean(embeddings, axis=0))

    @staticmethod
    def _cos_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Computes Cosine Similarity between two L2 normalized vectors.
        """
        return float(np.dot(v1, v2))

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(v))
        return v / (n + 1e-8)
