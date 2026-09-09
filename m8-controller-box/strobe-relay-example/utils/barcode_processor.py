"""
Barcode Processing Module
------------------------

Handles:
• Barcode detection using pyzbar
• Debounce (avoid repeated triggers for same barcode)
• Multi-frame confirmation
"""

import time
import cv2
from pyzbar.pyzbar import decode


class BarcodeProcessor:
    def __init__(self):
        # ----------------------------------------------------
        # Debounce settings
        # ----------------------------------------------------
        self.cooldown_seconds = 3.0   # ignore same barcode for this time
        self.last_seen = {}           # {barcode_data: timestamp}

        # ----------------------------------------------------
        # Multi-frame confirmation
        # ----------------------------------------------------
        self.required_frames = 3
        self.frame_counts = {}        # {barcode_data: count}

    def preprocess(self, frame):
        """
        Improve detection robustness
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Histogram equalization improves contrast
        gray = cv2.equalizeHist(gray)

        return gray

    def decode_barcodes(self, frame):
        """
        Detect and decode barcodes
        """
        processed = self.preprocess(frame)
        return decode(processed)

    def filter_valid_barcodes(self, barcodes):
        """
        Apply:
        • Multi-frame confirmation
        • Debounce logic
        """
        valid = []
        now = time.time()

        for bc in barcodes:
            data = bc.data.decode("utf-8")

            # ------------------------------------------------
            # Multi-frame confirmation
            # ------------------------------------------------
            self.frame_counts[data] = self.frame_counts.get(data, 0) + 1

            if self.frame_counts[data] < self.required_frames:
                continue

            # ------------------------------------------------
            # Debounce (cooldown)
            # ------------------------------------------------
            last_time = self.last_seen.get(data, 0)

            if now - last_time < self.cooldown_seconds:
                continue

            # Accept barcode
            self.last_seen[data] = now
            self.frame_counts[data] = 0
            valid.append((data, bc))

        return valid

    def draw_barcodes(self, frame, barcodes):
        """
        Draw bounding boxes + text
        """
        for data, bc in barcodes:
            x, y, w, h = bc.rect

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.putText(
                frame,
                data,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )