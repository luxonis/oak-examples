import logging
import threading
import time
from enum import Enum
from typing import List

import depthai as dai


class OutputType(Enum):
    FRAME = 0
    DETECTION = 1
    UNKNOWN = 2


class AnnotationNode(dai.node.HostNode):
    def __init__(
        self,
    ):
        super().__init__()
        self.output_names = []

        self.frames = {}  # key -> ImgFrame
        self.output_frames = {"passthrough": self.createOutput()}

        self.detections = {}  # key -> dai.ImgDetections
        self.output_detections = {}

        self._pred_count = 0
        self._pred_window_start = None
        self._stopping = threading.Event()
        self._state_lock = threading.Lock()

        self._logger = logging.getLogger(self.__class__.__name__)

    def build(self, cam, output_names: List[str]):
        self.link_args(cam)
        self.output_names = list(output_names)

        log_output = []
        for key in self.output_names:
            output_type = self._parse_key(key)
            log_output.append((key, output_type))
            if output_type == OutputType.FRAME:
                self.output_frames[key] = self.createOutput()
            elif output_type == OutputType.DETECTION:
                self.output_detections[key] = self.createOutput()

        self._logger.info(f"Workflow outputs: {log_output}")

        return self

    def process(self, cam):
        """Publish the latest workflow outputs without leaking shutdown errors."""
        if self._stopping.is_set():
            return

        try:
            transformation = cam.getTransformation()
            with self._state_lock:
                frames = list(self.frames.items())
                detections = list(self.detections.items())

            # The pipeline may be stopped between any of these sends.  A
            # closed queue is normal during a workflow-schema rebuild and must
            # not escape a HostNode callback (DepthAI aborts the process).
            for key, frame in frames:
                if self._stopping.is_set():
                    return
                frame.setTransformation(transformation)
                self.output_frames[key].send(frame)

            for key, detections_message in detections:
                if self._stopping.is_set():
                    return
                detections_message.setTransformation(transformation)
                self.output_detections[key].send(detections_message)
        except Exception:
            if not self._stopping.is_set():
                self._logger.exception("Failed to publish workflow annotations")

    def stop_processing(self):
        """Prevent HostNode callbacks from using queues being torn down."""
        self._stopping.set()

    def on_prediction(self, result, frame):
        """Process Roboflow output to DAI output"""

        self._log_throughput()

        dai_frame = dai.ImgFrame()
        dai_frame.setCvFrame(frame.image, dai.ImgFrame.Type.NV12)
        with self._state_lock:
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
                with self._state_lock:
                    self.frames[key] = vis_frame

            elif output_type == OutputType.DETECTION:
                dets = dai.ImgDetections()
                try:
                    parsed_dets = []
                    for det in value:
                        # Roboflow prediction output: xyxy, mask, conf, class_id, tracker, extra
                        xyxy, _, conf, class_id, _, extra = det

                        new_det = dai.ImgDetection()

                        h, w = extra["image_dimensions"]
                        class_label = extra["class_name"]

                        # normalize
                        x0, y0, x1, y1 = xyxy
                        x0 /= w
                        x1 /= w
                        y0 /= h
                        y1 /= h

                        new_det.xmin = float(x0)
                        new_det.ymin = float(y0)
                        new_det.xmax = float(x1)
                        new_det.ymax = float(y1)

                        new_det.confidence = float(conf)
                        new_det.label = int(class_id)
                        new_det.labelName = str(class_label)

                        parsed_dets.append(new_det)

                    # NOTE: `dets.detections` returns a copy - appending to it
                    # directly would be silently ignored, assign the full list.
                    dets.detections = parsed_dets
                except Exception:
                    self._logger.info(
                        f"Failed to parse output `{key}` as ImgDetection. "
                        "Verify that this output contains a valid Roboflow Detection. "
                        "If it does not, consider renaming the output in your Workflow so that "
                        "'predictions' is not a substring of the output name."
                    )

                with self._state_lock:
                    self.detections[key] = dets

    def _log_throughput(self, every: int = 100):
        """Periodically log the end-to-end workflow prediction rate"""
        if self._pred_window_start is None:
            self._pred_window_start = time.monotonic()
            return
        self._pred_count += 1
        if self._pred_count % every == 0:
            elapsed = time.monotonic() - self._pred_window_start
            self._logger.info(
                f"Roboflow workflow throughput: {every / elapsed:.2f} predictions/s"
            )
            self._pred_window_start = time.monotonic()

    def _parse_key(self, key: str):
        """Parse the key to a output type"""
        if "visualization" in key:
            return OutputType.FRAME
        elif "predictions" in key:
            return OutputType.DETECTION
        else:
            return OutputType.UNKNOWN
