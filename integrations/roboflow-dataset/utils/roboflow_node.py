import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

import depthai as dai
import numpy as np

from utils.roboflow_uploader import RoboflowUploader


class RoboflowNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        # Executor to handle uploads asynchronously
        # For real-time uploads at ~10Hz we spawn 40 threads
        self.executor = ThreadPoolExecutor(max_workers=40)
        self.last_upload_time = time.monotonic()
        self.current_dets: Optional[dai.ImgDetections] = None
        self.current_frame: Optional[np.ndarray] = None

    def build(
        self,
        preview: dai.Node.Output,
        nn: dai.Node.Output,
        uploader: RoboflowUploader,
        auto_interval: Optional[float] = None,
        auto_threshold: Optional[float] = None,
        labels: Optional[List[str]] = None,
    ) -> "RoboflowNode":
        self.link_args(preview, nn)

        self.uploader = uploader
        self.auto_interval = auto_interval
        self.auto_threshold = auto_threshold
        self.autoupload = auto_interval is not None and auto_threshold is not None

        if self.autoupload:
            print(f"Auto-uploading to Roboflow every {self.auto_interval} seconds")

        self.labels = labels
        return self

    def process(self, preview: dai.Buffer, dets: dai.ImgDetections) -> None:
        frame = preview.getCvFrame()
        shape = (frame.shape[1], frame.shape[0])

        self.current_dets = dets
        self.current_frame = frame

        dt = time.monotonic() - self.last_upload_time

        if self.autoupload and dt > self.auto_interval:
            # Auto-upload annotations with confidence above self.auto_threshold every self.auto_interval seconds
            shape = (frame.shape[1], frame.shape[0])
            labels, bboxes = self.parse_dets(
                dets.detections, shape, confidence_thr=self.auto_threshold
            )

            if len(bboxes) > 0:
                print(f"Auto-uploading grabbed frame with {len(bboxes)} annotations!")
                self.upload_dets(self.current_frame, labels, bboxes)
            else:
                print(
                    f"No detections with confidence above {self.auto_threshold}. Not uploading!"
                )

            self.last_upload_time = time.monotonic()

    def handle_key(self, key):
        if key == ord(" "):
            if self.current_dets is None or self.current_frame is None:
                return
            # If Space is pressed, upload all detections without thresholding
            shape = (self.current_frame.shape[1], self.current_frame.shape[0])
            labels, bboxes = self.parse_dets(
                self.current_dets.detections, shape, confidence_thr=0.0
            )

            print("Space pressed. Uploading grabbed frame!")
            self.upload_dets(self.current_frame, labels, bboxes)

    def parse_dets(
        self,
        detections: List[dai.ImgDetection],
        image_shape: Tuple[int, int],
        confidence_thr: float,
    ) -> Tuple[List[str], List[Tuple[int, int, int, int]]]:
        width, height = image_shape
        if self.labels is not None:
            labels = [
                self.labels[d.label]
                for d in detections
                if d.confidence > confidence_thr
            ]
        else:
            labels = [str(d.label) for d in detections if d.confidence > confidence_thr]

        bboxes = [
            [width * d.xmin, height * d.ymin, width * d.xmax, height * d.ymax]
            for d in detections
            if d.confidence > confidence_thr
        ]

        return labels, bboxes

    def upload_dets(
        self,
        frame: np.ndarray,
        labels: List[str],
        bboxes: List[Tuple[int, int, int, int]],
    ):
        future = self.executor.submit(self.uploader.upload, frame, labels, bboxes)
        future.add_done_callback(lambda _: print("Upload finished!"))
