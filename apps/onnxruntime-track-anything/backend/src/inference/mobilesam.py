import cv2
import numpy as np


class MobileSamSelector:
    """Select a target mask in a frozen camera frame using MobileSAM prompts."""

    def __init__(self, sessions):
        """Use the shared QNN session manager for all selection graphs."""
        self.sessions = sessions
        self.decoder_name = None

    def load_models(self):
        """Load the image encoder and initial one-point decoder."""
        self.sessions.get("mobilesam/encoder")
        self._load_decoder(1)

    def _load_decoder(self, count):
        """Keep only the active prompt-count decoder resident in memory."""
        name = f"mobilesam/decoder_points_{count}_v1"
        if self.decoder_name != name:
            if self.decoder_name is not None:
                self.sessions.unload(self.decoder_name)
            self.decoder_name = None
            self.sessions.get(name)
            self.decoder_name = name
        return name

    def encode_selection(self, bgr):
        """Encode a frozen frame once for repeated MobileSAM prompt refinement.

        Args:
            bgr: Source camera image as an HWC BGR array.

        Returns:
            Tuple of image embedding, resized (height, width), and original
            (height, width). These dimensions undo the encoder's square padding.
        """
        h, w = bgr.shape[:2]
        rh, rw = round(h * 1024 / max(h, w)), round(w * 1024 / max(h, w))
        rgb = (
            cv2.cvtColor(cv2.resize(bgr, (rw, rh)), cv2.COLOR_BGR2RGB).astype(
                np.float32
            )
            / 255
        )

        # Mean-color padding becomes zero after normalization inside the export.
        padded = np.empty((1024, 1024, 3), np.float32)
        padded[:] = np.array([123.675, 116.28, 103.53], np.float32) / 255
        padded[:rh, :rw] = rgb
        embedding = self.sessions.run(
            "mobilesam/encoder", image=padded.transpose(2, 0, 1)[None]
        )[0]
        return embedding, (rh, rw), (h, w)

    def select(self, encoded, points):
        """Decode prompts and map the selected mask back to the source frame.

        Args:
            encoded: Embedding and dimensions returned by ``encode_selection``.
            points: Validated dictionaries with normalized x/y coordinates and
                MobileSAM labels (0/1 for clicks, 2/3 for box corners).

        Returns:
            Boolean mask at the original frame size and the model's mask score.
        """
        embedding, (rh, rw), (h, w) = encoded
        coords = np.array([[[p["x"] * rw, p["y"] * rh] for p in points]], np.float32)
        labels = np.array([[p["label"] for p in points]], np.float32)

        decoder = self._load_decoder(len(points))
        masks, scores = self.sessions.run(
            decoder,
            image_embeddings=embedding,
            point_coords=coords,
            point_labels=labels,
        )

        # SAM's single-mask rule: ambiguous single/two-point prompts prefer
        # multimask candidates; boxes or >=3 clicks use the single-mask token.
        index = (
            0
            if len(points) >= 3 or any(p["label"] == 2 for p in points)
            else 1 + int(np.argmax(scores[0, 1:]))
        )

        logits = cv2.resize(masks[0, index], (1024, 1024))[:rh, :rw]
        return cv2.resize(logits, (w, h)) > 0, float(scores[0, index])
