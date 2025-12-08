from datetime import timedelta

import depthai as dai
import numpy as np
from pyzbar.pyzbar import decode

from utils.qr_detections import QRDetection, QRDetections

DECODE = True


class QRScanner(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.tile_positions = None
        self._out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )
        self._out_grid = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self, preview: dai.Node.Output, nn: dai.Node.Output, tile_positions
    ) -> "QRScanner":
        self.link_args(preview, nn)
        self.tile_positions = tile_positions
        return self

    def process(self, preview, detections) -> None:
        frame = preview.getCvFrame()

        qr_dets = QRDetections()
        for det in detections.detections:
            qr_det = QRDetection()
            qr_det.confidence = det.confidence
            qr_det.xmin = det.xmin
            qr_det.xmax = det.xmax
            qr_det.ymin = det.ymin
            qr_det.ymax = det.ymax

            if DECODE:
                bbox = frame_denorm(frame, (det.xmin, det.ymin, det.xmax, det.ymax))
                decoded_text = self.decode(frame, bbox)
                if decoded_text:
                    qr_det.label = decoded_text
            qr_dets.detections.append(qr_det)

        qr_dets.setSequenceNum(detections.getSequenceNum())
        qr_dets.setTimestamp(detections.getTimestamp())
        grid_annot = self.draw_grid(frame, detections.getTimestamp())
        self.out_grid.send(grid_annot)
        self.out.send(qr_dets)

    def decode(self, frame, bbox):
        """
        Decode the QR code present in the given bounding box.
        """
        assert DECODE
        if bbox[1] == bbox[3] or bbox[0] == bbox[2]:
            print("Detection bbox is empty")
            return ""

        bbox = expand_bbox(bbox, frame, 5)  # expand bbox by 5%
        img = frame[bbox[1] : bbox[3], bbox[0] : bbox[2]]

        data = decode(img)
        if data:
            text = data[0].data.decode("utf-8")
            print("Decoded text", text)
            return text
        else:
            print("Decoding failed")
            return ""

    def draw_grid(self, frame: np.ndarray, timestamp: timedelta) -> None:
        if not self.tile_positions:
            print("Error: Tile positions are not set.")
            return

        img_height, img_width, _ = frame.shape

        np.random.seed(432)
        colors = [
            dai.Color(np.random.random(), np.random.random(), np.random.random(), 0.3)
            for _ in range(len(self.tile_positions))
        ]
        img_annots = dai.ImgAnnotations()
        img_annot = dai.ImgAnnotation()

        for idx, tile_info in enumerate(self.tile_positions):
            x1, y1, x2, y2 = tile_info
            color = colors[idx % len(colors)]
            rect = dai.PointsAnnotation()
            rect.fillColor = color
            pts = [
                dai.Point2f(x1 / img_width, y1 / img_height),
                dai.Point2f(x1 / img_width, y2 / img_height),
                dai.Point2f(x2 / img_width, y2 / img_height),
                dai.Point2f(x2 / img_width, y1 / img_height),
            ]
            rect.points.extend(pts)
            rect.type = dai.PointsAnnotationType.LINE_LOOP
            img_annot.points.append(rect)

        grid_info_annot = dai.TextAnnotation()
        grid_info_annot.fontSize = 25
        grid_info_annot.text = f"Tiles: {len(self.tile_positions)}"
        grid_info_annot.position = dai.Point2f(0.05, 0.05)
        grid_info_annot.textColor = dai.Color(0.0, 0.0, 0.0)
        grid_info_annot.backgroundColor = dai.Color(0.0, 1.0, 0.0)
        img_annot.texts.append(grid_info_annot)

        img_annots.annotations.append(img_annot)
        img_annots.setTimestamp(timestamp)

        return img_annots

    @property
    def out(self):
        return self._out

    @property
    def out_grid(self):
        return self._out_grid


def expand_bbox(bbox: np.ndarray, frame: np.ndarray, percentage: float) -> np.ndarray:
    """
    Expand the bounding box by a certain percentage.
    """
    bbox_copy = bbox.copy()
    pixels_expansion_0 = (bbox_copy[3] - bbox_copy[1]) * (percentage / 100)
    pixels_expansion_1 = (bbox_copy[2] - bbox_copy[0]) * (percentage / 100)
    bbox_copy[0] = max(0, bbox_copy[0] - pixels_expansion_1)
    bbox_copy[1] = max(0, bbox_copy[1] - pixels_expansion_0)
    bbox_copy[2] = min(frame.shape[1], bbox_copy[2] + pixels_expansion_1)
    bbox_copy[3] = min(frame.shape[0], bbox_copy[3] + pixels_expansion_0)
    return bbox_copy


def frame_denorm(frame, bbox):
    norm_vals = np.full(len(bbox), frame.shape[0])
    norm_vals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * norm_vals).astype(int)
