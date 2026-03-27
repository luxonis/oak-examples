import depthai as dai
from depthai_nodes.utils import AnnotationHelper


class OCRAnnotationNode(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()

        self.input = self.createInput()
        self.passthrough = self.createInput()

        self.frame_output = self.createOutput()
        self.text_annotations_output = self.createOutput()

    def run(self):
        while self.isRunning():
            text_descriptions = self.input.get()
            passthrough_frame = self.passthrough.get()

            detections_list = text_descriptions.reference_data.detections
            recognitions_list = text_descriptions.items

            w, h = passthrough_frame.getWidth(), passthrough_frame.getHeight()

            if len(recognitions_list) >= 1:
                annotation_helper = AnnotationHelper()

                for i, recognition in enumerate(recognitions_list):
                    detection = detections_list[i]
                    points = detection.getBoundingBox().getPoints()

                    text_line = ""
                    for text, score in zip(recognition.classes, recognition.scores):
                        if len(text) <= 2 or score < 0.25:
                            continue

                        text_line += text + " "

                    size = int(points[3].y * h - points[0].y * h)
                    annotation_helper.draw_text(
                        text_line, [points[3].x + 0.02, points[3].y + 0.02], size=size
                    )

                annotations = annotation_helper.build(
                    text_descriptions.getTimestamp(), text_descriptions.getSequenceNum()
                )

            self.frame_output.send(passthrough_frame)
            if len(recognitions_list) >= 1:
                self.text_annotations_output.send(annotations)
