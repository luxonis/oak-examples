import logging
from typing import List

import depthai as dai

from config.config import PipelineConfig
from core.annotation_node import AnnotationNode
from core.frame_producer import DepthAIFrameProducer
from core.visualizer_wrapper import VisualizerWrapper


class DepthAIPipeline:
    def __init__(
        self,
        pipeline_config: PipelineConfig,
        visualizer: VisualizerWrapper,
        workflow_output_names: List[str],
    ):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._pipeline_config = pipeline_config
        self._visualizer = visualizer
        self.workflow_output_names = workflow_output_names

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
                cam=frames, output_names=workflow_output_names
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

    def create_frame_producer(self) -> DepthAIFrameProducer:
        """Factory passed to InferencePipeline as `video_reference`"""
        width, height = self._pipeline_config.output_size
        return DepthAIFrameProducer(
            queue=self._queue,
            width=width,
            height=height,
            fps=self._pipeline_config.fps,
        )

    def start(self):
        self._pipeline.start()
        self._logger.info("DepthAI pipeline started")

    def stop(self):
        self._pipeline.stop()
        self._logger.info("DepthAI pipeline stopped")
