from time import perf_counter

import cv2
import numpy as np

HEIGHT, WIDTH = 320, 576


def image_tensor(bgr):
    """Convert a BGR frame to RGB float32 in [0, 1], shaped (1, 3, 320, 576)."""
    rgb = cv2.cvtColor(cv2.resize(bgr, (WIDTH, HEIGHT)), cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255


class XMemMemory:
    """First-frame anchor plus four recent memories, with full-softmax XMem readout.

    The similarity equation follows XMem (MIT); unlike the full upstream
    long-term consolidation algorithm this example uses a bounded FIFO.
    """

    def __init__(self, capacity=5):
        self.capacity = capacity
        self.entries = []

    def add(self, key, shrinkage, value):
        """Store one encoded frame, retaining the first-frame anchor on eviction."""
        self.entries.append(
            (key.reshape(64, -1), shrinkage.reshape(-1, 1), value.reshape(512, -1))
        )
        if len(self.entries) > self.capacity:
            # Entry zero anchors the original selection; evict the oldest update.
            del self.entries[1]

    def read(self, key, selection, sessions=None):
        """Retrieve stored features using XMem's weighted key similarity.

        Args:
            key: Query key tensor with 64 channels on the 20 x 36 feature grid.
            selection: Per-channel query weights on the same grid.
            sessions: QNN sessions used by the app. None selects the NumPy
                reference implementation for numerical tests.

        Returns:
            Memory readout shaped (1, 1, 512, 20, 36).
        """
        mk = np.concatenate([x[0] for x in self.entries], axis=1).T
        ms = np.concatenate([x[1] for x in self.entries], axis=0)
        values = np.concatenate([x[2] for x in self.entries], axis=1)
        qk, qe = key.reshape(64, -1), selection.reshape(64, -1)

        if sessions is not None:
            return sessions.run(
                f"track_anything/memory_read_{len(self.entries)}_v1",
                memory_key=mk,
                memory_shrinkage=ms,
                memory_value=values,
                query_key=qk,
                query_selection=qe,
            )[0]

        # NumPy reference retained for independent equation/graph verification.
        similarity = (
            (
                -(mk * mk) @ qe
                + 2 * (mk @ (qk * qe))
                - (qe * qk * qk).sum(axis=0, keepdims=True)
            )
            * ms
            / 8
        )

        similarity -= similarity.max(axis=0, keepdims=True)
        affinity = np.exp(similarity)
        affinity /= affinity.sum(axis=0, keepdims=True)
        return (values @ affinity).reshape(1, 1, 512, 20, 36)


class XMemTracker:
    """Propagate one object's mask with recurrent state and bounded XMem memory."""

    def __init__(self, sessions):
        self.sessions = sessions
        self.memory = XMemMemory()
        self.hidden = np.zeros((1, 1, 64, 20, 36), np.float32)
        self.steps = 0
        self.timings = {}

    @staticmethod
    def load_models(sessions):
        """Load tracking networks and all five bounded-memory graph variants."""
        for part in (
            "encode_key_with_shrinkage",
            "encode_key_without_shrinkage",
            "encode_value",
            "segment",
        ):
            sessions.get(f"track_anything/{part}")
        for count in range(1, 6):
            sessions.get(f"track_anything/memory_read_{count}_v1")

    def initialize(self, frame, mask):
        """Seed a new tracker with the selected frame and its mask.

        Args:
            frame: Source camera image as an HWC BGR array.
            mask: Boolean target mask aligned with the source frame.
        """
        image = image_tensor(frame)
        # Memory entries need shrinkage weights; this export also supplies f16.
        key, shrinkage, _, f16 = self.sessions.run(
            "track_anything/encode_key_with_shrinkage", image=image
        )

        mask = cv2.resize(
            mask.astype(np.float32), (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST
        )
        _, value, self.hidden = self.sessions.run(
            "track_anything/encode_value",
            image=image,
            mask=mask[None],
            f16=f16,
            hidden_state=self.hidden,
        )
        self.memory.add(key, shrinkage, value)

    def step(self, frame):
        """Advance tracking by one BGR frame and record stage timings.

        Args:
            frame: Next camera image as an HWC BGR array.

        Returns:
            Boolean mask shaped (320, 576) and mean foreground probability
            within that mask, or zero confidence when the mask is empty.
        """
        start = perf_counter()
        image = image_tensor(frame)
        pre = perf_counter()

        # Per-frame segmentation needs f16/f8/f4, exposed by this query encoder.
        key, selection, f16, f8, f4 = self.sessions.run(
            "track_anything/encode_key_without_shrinkage", image=image
        )
        encoded = perf_counter()

        memory = self.memory.read(key, selection, self.sessions)
        read = perf_counter()

        probs, self.hidden = self.sessions.run(
            "track_anything/segment",
            f16=f16,
            f8=f8,
            f4=f4,
            memory_readout=memory,
            hidden_state=self.hidden,
        )
        decoded = perf_counter()

        mask = probs[1] > probs[0]
        area = int(mask.sum())
        self.steps += 1

        # Avoid writing an empty/lost prediction into the reference memory.
        if self.steps % 5 == 0 and area >= 32:
            mkey, shrinkage, _, mf16 = self.sessions.run(
                "track_anything/encode_key_with_shrinkage", image=image
            )
            _, value, self.hidden = self.sessions.run(
                "track_anything/encode_value",
                image=image,
                mask=mask.astype(np.float32)[None],
                f16=mf16,
                hidden_state=self.hidden,
            )
            self.memory.add(mkey, shrinkage, value)

        end = perf_counter()
        self.timings = {
            "preprocess_ms": (pre - start) * 1000,
            "encode_ms": (encoded - pre) * 1000,
            "memory_ms": (read - encoded) * 1000,
            "decode_ms": (decoded - read) * 1000,
            "update_ms": (end - decoded) * 1000,
            "inference_ms": (end - start) * 1000,
        }
        return mask, float(probs[1][mask].mean()) if area else 0
