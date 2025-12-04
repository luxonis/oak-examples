import depthai as dai
import cv2
import threading
import logging
from typing import Dict

from core.annotation_node import AnnotationNode
from core.generator_capture import GeneratorCapture
from config.config import PipelineConfig
from core.visualizer_wrapper import VisualizerWrapper


class DepthAIPipeline:
    def __init__(
        self,
        pipeline_config: PipelineConfig,
        visualizer: VisualizerWrapper,
        workflow_schema: Dict,
    ):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._stop_event = threading.Event()
        self._orig_capture = cv2.VideoCapture
        self._pipeline_config = pipeline_config
        self._visualizer = visualizer
        self.workflow_schema = workflow_schema

        device_ip = self._pipeline_config.device
        self._device = (
            dai.Device(dai.DeviceInfo(device_ip)) if device_ip else dai.Device()
        )
        with dai.Pipeline(self._device) as p:
            cam = p.create(dai.node.Camera)
            cam.build()

            width, height = self._pipeline_config.output_size
            frames = cam.requestOutput(
                (width, height),
                dai.ImgFrame.Type.RGB888i,
                fps=self._pipeline_config.fps,
            )
            self._queue = frames.createOutputQueue()

            # Annotation node
            self.annotation = p.create(AnnotationNode).build(
                cam=frames, schema=workflow_schema
            )

            # Visualization
            encoders = {}
            for key in self.annotation.output_frames.keys():
                encoders[key] = p.create(dai.node.VideoEncoder).build(
                    input=self.annotation.output_frames[key],
                    frameRate=self._pipeline_config.fps,
                    profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
                )
                self._visualizer.add_topic(key, encoders[key].out)

            for key in self.annotation.output_detections.keys():
                topic = self.annotation.output_detections[key]
                self._visualizer.add_topic(key, topic)

            self._pipeline = p

    def _frame_gen(self):
        """Generator of DAI input frames"""
        while self._pipeline.isRunning() and not self._stop_event.is_set():
            try:
                frame = self._queue.get().getCvFrame()
            except Exception:
                break

            if frame is not None:
                yield frame

    def start(self):
        cv2.VideoCapture = lambda _: GeneratorCapture(self._frame_gen())
        self._pipeline.start()
        self._logger.info("DepthAI pipeline started")

    def stop(self):
        self._stop_event.set()
        cv2.VideoCapture = self._orig_capture
        self._pipeline.stop()
        self._logger.info("DepthAI pipeline stopped")
