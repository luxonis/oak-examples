import depthai as dai
from depthai_nodes.utils import AnnotationHelper


class OCRAnnotationNode(dai.node.HostNode):
    def __init__(self):
        super().__init__()

        self.frame_output = self.createOutput()
        self.text_annotations_output = self.createOutput()

        self.min_confidence = 0.0
        self.min_text_length = 1

    def build(
        self,
        frame_output: dai.Node.Output,
        gathered_output: dai.Node.Output,
        min_confidence: float = 0.0,
        min_text_length: int = 1,
    ) -> "OCRAnnotationNode":
        self.link_args(frame_output, gathered_output)
        self.min_confidence = min_confidence
        self.min_text_length = min_text_length
        return self

    def process(self, frame: dai.ImgFrame, gathered: dai.Buffer) -> None:
        sequence_num = gathered.getSequenceNum()
        # HostNode syncs timestamps; reject any pair with different frame IDs.
        if frame.getSequenceNum() != sequence_num:
            return

        helper = AnnotationHelper()
        detections = gathered.reference_data.detections
        recognitions = gathered.items
        for detection, recognition in zip(detections, recognitions):
            parts = [part.strip() for part in recognition.classes if part.strip()]
            text = " ".join(parts)
            scores = [float(score) for score in recognition.scores]
            confidence = min(scores) if scores else 0.0
            points = detection.getBoundingBox().getPoints()
            shown = (
                bool(text)
                and len(text) >= self.min_text_length
                and confidence >= self.min_confidence
            )
            if not shown:
                continue

            helper.draw_polyline(points, fill_color=None, thickness=2, closed=True)
            x0 = max(0.0, min(p.x for p in points))
            y0 = max(0.0, min(p.y for p in points))
            y1 = min(1.0, max(p.y for p in points))
            y = y0 - 0.01 if y0 > 0.07 else min(0.98, y1 + 0.01)
            size = max(16, min(28, int((y1 - y0) * frame.getHeight() * 0.8)))
            helper.draw_text(
                f"{text}  {confidence:.2f}",
                (min(0.98, x0), y),
                size=size,
            )

        annotations = helper.build(gathered.getTimestamp(), sequence_num)
        self.frame_output.send(frame)
        self.text_annotations_output.send(annotations)
