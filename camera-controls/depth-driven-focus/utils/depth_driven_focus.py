import math

import depthai as dai

LENS_STEP = 3

TEXT_COLOR = (1.0, 1.0, 1.0, 1.0)
BACKGROUND_COLOR = (0.0, 0.0, 0.0, 1.0)


class DepthDrivenFocus(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._lens_pos = 150
        self._lens_min = 0
        self._lens_max = 255
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self, control_queue: dai.Node.Output, face_detection: dai.Node.Output
    ) -> "DepthDrivenFocus":
        self.link_args(face_detection)
        self.control_queue = control_queue
        self.sendProcessingToPipeline(False)
        return self

    def process(self, face_detection: dai.SpatialImgDetections) -> None:
        closest_dist = None
        for detection in face_detection.detections:
            try:
                dist = int(calculate_distance(detection.spatialCoordinates))
                if closest_dist is None or dist < closest_dist:
                    closest_dist = dist
            except ValueError:
                print("Invalid depth value")

        if closest_dist is not None:
            new_lens_pos = max(
                self._lens_min, min(get_lens_position(closest_dist), self._lens_max)
            )
            if new_lens_pos != self._lens_pos and new_lens_pos != 255:
                self._lens_pos = new_lens_pos

                print("Setting automatic focus, lens position: ", new_lens_pos)
                ctrl = dai.CameraControl()
                ctrl.setManualFocus(self._lens_pos)
                self.control_queue.send(ctrl)

        img_annotations = dai.ImgAnnotations()
        annotation = dai.ImgAnnotation()
        text_dist_annot = dai.TextAnnotation()
        if closest_dist is not None:
            text_dist_annot.text = f"Face distance: {closest_dist / 1000:.2f} m"
        else:
            text_dist_annot.text = "Face distance: Not detected"
        text_dist_annot.fontSize = 15
        text_dist_annot.textColor = dai.Color(*TEXT_COLOR)
        text_dist_annot.backgroundColor = dai.Color(*BACKGROUND_COLOR)
        text_dist_annot.position = dai.Point2f(0.05, 0.05, True)
        annotation.texts.append(text_dist_annot)

        text_lens_annot = dai.TextAnnotation()
        text_lens_annot.text = f"Lens position: {self._lens_pos:.2f}"
        text_lens_annot.fontSize = 15
        text_lens_annot.textColor = dai.Color(*TEXT_COLOR)
        text_lens_annot.backgroundColor = dai.Color(*BACKGROUND_COLOR)
        text_lens_annot.position = dai.Point2f(0.05, 0.1, True)
        annotation.texts.append(text_lens_annot)
        img_annotations.annotations.append(annotation)
        img_annotations.setTimestamp(face_detection.getTimestamp())

        self.output.send(img_annotations)


def get_lens_position(dist):
    # = 150 - A10*0.0242 + 0.00000412*A10^2
    return int(150 - dist * 0.0242 + 0.00000412 * dist**2)


def calculate_distance(coords):
    return math.sqrt(coords.x**2 + coords.y**2 + coords.z**2)
