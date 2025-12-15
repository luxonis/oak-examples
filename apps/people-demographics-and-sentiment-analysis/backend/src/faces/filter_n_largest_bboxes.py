import depthai as dai
from depthai_nodes import ImgDetectionsExtended


class FilterNLargestBBoxes(dai.node.HostNode):
    """
    Keep only the N largest detections by area (width * height of rotated_rect).
    """

    def __init__(self):
        super().__init__()
        self.n_face_crops: int = 4

    def build(
        self, face_detections: dai.Node.Output, n_face_crops: int = 4
    ) -> "FilterNLargestBBoxes":
        if n_face_crops < 1:
            raise ValueError("n_face_crops must be >= 1")
        self.n_face_crops = n_face_crops
        self.link_args(face_detections)
        return self

    def process(self, face_detections: dai.Buffer) -> None:
        assert isinstance(
            face_detections, ImgDetectionsExtended
        ), f"Expected ImgDetectionsExtended, got {type(face_detections)}"

        detections = face_detections.detections
        if not detections or len(detections) < self.n_face_crops:
            self.out.send(face_detections)
            return

        detections.sort(key=self._area, reverse=True)
        n_detections = detections[: self.n_face_crops]

        filtered_detections = ImgDetectionsExtended()
        filtered_detections.detections = n_detections
        filtered_detections.setTimestamp(face_detections.getTimestamp())
        filtered_detections.setSequenceNum(face_detections.getSequenceNum())
        self.out.send(filtered_detections)

    @staticmethod
    def _area(det: ImgDetectionsExtended) -> float:
        rr = det.rotated_rect
        return rr.size.width * rr.size.height
