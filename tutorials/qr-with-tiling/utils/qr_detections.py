import depthai as dai


class QRDetection(dai.Buffer):
    def __init__(self):
        super().__init__()
        self.label: str = ""
        self.xmin: float = 0
        self.ymin: float = 0
        self.xmax: float = 0
        self.ymax: float = 0
        self.confidence: float = 0


class QRDetections(dai.Buffer):
    def __init__(self):
        super().__init__()
        self.detections: list[QRDetection] = []

    def getVisualizationMessage(self):
        img_annots = dai.ImgAnnotations()
        img_annot = dai.ImgAnnotation()
        for det in self.detections:
            pts_annot = dai.PointsAnnotation()
            bbox_pts = [
                dai.Point2f(det.xmin, det.ymin),
                dai.Point2f(det.xmin, det.ymax),
                dai.Point2f(det.xmax, det.ymax),
                dai.Point2f(det.xmax, det.ymin),
            ]
            pts_annot.points.extend(bbox_pts)
            pts_annot.outlineColor = dai.Color(0.0, 1.0, 0.0)
            pts_annot.type = dai.PointsAnnotationType.LINE_LOOP
            pts_annot.thickness = 2
            img_annot.points.append(pts_annot)

            txt_annot = dai.TextAnnotation()
            txt_annot.fontSize = 25

            txt_annot.text = f"{det.label} {round(det.confidence * 100):<3}%"
            txt_annot.position = dai.Point2f(det.xmin, det.ymin)
            txt_annot.textColor = dai.Color(0.0, 0.0, 0.0)
            txt_annot.backgroundColor = dai.Color(0.0, 1.0, 0.0)
            img_annot.texts.append(txt_annot)
        img_annots.annotations.append(img_annot)
        img_annots.setBufferMetadataFrom(self)
        return img_annots
