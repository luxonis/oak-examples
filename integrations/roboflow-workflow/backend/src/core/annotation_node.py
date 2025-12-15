import logging
import depthai as dai
from enum import Enum
from depthai_nodes import ImgDetectionsExtended, ImgDetectionExtended


class OutputType(Enum):
    FRAME = 0
    DETECTION = 1
    UNKNOWN = 2


class AnnotationNode(dai.node.HostNode):
    def __init__(
        self,
    ):
        super().__init__()
        self.schema_keys = []

        self.frames = {}  # key -> ImgFrame
        self.output_frames = {"passthrough": self.createOutput()}

        self.detections = {}  # key -> ImgDetectionsExtended
        self.output_detections = {}

        self._logger = logging.getLogger(self.__class__.__name__)

    def build(self, cam, schema):
        self.link_args(cam)
        self.schema_keys = list(schema.keys())

        log_output = []
        for key in self.schema_keys:
            output_type = self._parse_key(key)
            log_output.append((key, output_type))
            if output_type == OutputType.FRAME:
                self.output_frames[key] = self.createOutput()
            elif output_type == OutputType.DETECTION:
                self.output_detections[key] = self.createOutput()

        self._logger.info(f"Schema keys: {log_output}")

        return self

    def process(self, cam):
        transformation = cam.getTransformation()

        # send the latest stored data for each schema key
        for key in self.frames.keys():
            self.frames[key].setTransformation(transformation)
            self.output_frames[key].send(self.frames[key])

        for key in self.detections.keys():
            self.detections[key].setTransformation(transformation)
            self.output_detections[key].send(self.detections[key])

    def on_prediction(self, result, frame):
        """Process Roboflow output to DAI output"""

        dai_frame = dai.ImgFrame()
        dai_frame.setCvFrame(frame.image, dai.ImgFrame.Type.NV12)
        self.frames["passthrough"] = dai_frame

        for key, value in result.items():
            output_type = self._parse_key(key)
            if output_type == OutputType.FRAME:
                vis_frame = dai.ImgFrame()
                try:
                    vis_frame.setCvFrame(
                        value.numpy_image,
                        dai.ImgFrame.Type.NV12,
                    )
                except Exception:
                    self._logger.info(
                        f"Failed to parse output `{key}` as ImgFrame. "
                        "Verify that this output contains a valid Roboflow WorkflowImageData. "
                        "If it does not, consider renaming the output in your Workflow so that "
                        "'visualization' is not a substring of the output name."
                    )
                self.frames[key] = vis_frame

            elif output_type == OutputType.DETECTION:
                dets = ImgDetectionsExtended()
                try:
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
                except Exception:
                    self._logger.info(
                        f"Failed to parse output `{key}` as ImgDetectionExtended. "
                        "Verify that this output contains a valid Roboflow Detection. "
                        "If it does not, consider renaming the output in your Workflow so that "
                        "'predictions' is not a substring of the output name."
                    )

                self.detections[key] = dets

    def _parse_key(self, key: str):
        """Parse the key to a output type"""
        if "visualization" in key:
            return OutputType.FRAME
        elif "predictions" in key:
            return OutputType.DETECTION
        else:
            return OutputType.UNKNOWN
