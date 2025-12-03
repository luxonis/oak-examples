import depthai as dai
from depthai_nodes import ImgDetectionsExtended, ImgDetectionExtended
import logging


class AnnotationNode(dai.node.HostNode):
    def __init__(
        self,
    ):
        super().__init__()
        self.schema_keys = []
        self.outputs = {"passthrough": self.createOutput()}
        self.frames = {}  # key -> ImgFrame
        self.detections = {}  # key -> ImgDetectionsExtended

        self._logger = logging.getLogger(self.__class__.__name__)

    def build(self, cam, schema):
        self.link_args(cam)

        self.schema_keys = list(schema.keys())
        self._logger.info(f"Schema keys: {self.schema_keys}")
        for key in self.schema_keys:
            self.outputs[key] = self.createOutput()

        return self

    def process(self, cam):
        transformation = cam.getTransformation()
        # send the latest stored data for each schema key
        for key, output in self.outputs.items():
            if key in self.frames:
                self.frames[key].setTransformation(transformation)
                output.send(self.frames[key])

            elif key in self.detections:
                self.detections[key].setTransformation(transformation)
                output.send(self.detections[key])

    def on_prediction(self, result, frame):
        """Process Roboflow output to DAI output"""

        dai_frame = dai.ImgFrame()
        dai_frame.setCvFrame(frame.image, dai.ImgFrame.Type.BGR888i)
        self.frames["passthrough"] = dai_frame

        result_dict = result.get("result") or result
        for key, value in result_dict.items():
            if "visualization" in key:
                vis_frame = dai.ImgFrame()
                vis_frame.setCvFrame(
                    value.numpy_image,
                    dai.ImgFrame.Type.BGR888i,
                )
                self.frames[key] = vis_frame

            elif "prediction" in key or "predictions" in key:
                dets = ImgDetectionsExtended()

                for det in value:
                    # Roboflow prediction output: xyxy, mask, conf, class_id, tracker, extra
                    xyxy, _, conf, class_id, _, extra = det

                    new_det = ImgDetectionExtended()

                    h, w = extra["image_dimensions"]
                    class_label = extra["class_name"]

                    # normalize
                    x0, y0, x1, y1 = xyxy
                    x0 /= w
                    x1 /= w
                    y0 /= h
                    y1 /= h

                    new_det.rotated_rect = (
                        float((x0 + x1) / 2),
                        float((y0 + y1) / 2),
                        float(x1 - x0),
                        float(y1 - y0),
                        0,
                    )

                    new_det.confidence = float(conf)
                    new_det.label = int(class_id)
                    new_det.label_name = str(class_label)

                    dets.detections.append(new_det)

                self.detections[key] = dets
