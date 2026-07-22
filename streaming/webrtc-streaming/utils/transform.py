import cv2
import depthai as dai
import numpy as np
from aiortc import VideoStreamTrack
from av import VideoFrame
from depthai_nodes.node import ParsingNeuralNetwork


class VideoTransform(VideoStreamTrack):
    def __init__(self, pipeline, application, pc_id, options):
        super().__init__()
        self.application = application
        self.pc_id = pc_id

        self.nn_flag = options.nn
        self.depth_flag = options.camera_type == "depth"

        self.pipeline = pipeline
        self.preview, self.nn, self.label_map = start_pipeline(self.pipeline, options)
        self.pipeline.start()

    async def recv(self):
        frame = await self.parse_frame()

        pts, time_base = await self.next_timestamp()
        new_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base

        return new_frame

    async def parse_frame(self):
        frame = (
            self.preview.get().getFrame()
            if self.depth_flag
            else self.preview.get().getCvFrame()
        )
        dets = self.nn.get().detections if self.nn is not None else []

        if self.depth_flag:
            frame = colorize_depth(frame)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        for detection in dets:
            if isinstance(detection, dai.ImgDetection):
                bbox = frameNorm(
                    frame,
                    (
                        detection.xmin,
                        detection.ymin,
                        detection.xmax,
                        detection.ymax,
                    ),
                )
            else:
                raise RuntimeError("Unknown detection type")

            if self.label_map is not None:
                label = self.label_map[detection.label]
            else:
                label = f"LABEL {detection.label}"
            cv2.putText(
                frame,
                label,
                (bbox[0] + 10, bbox[1] + 20),
                cv2.FONT_HERSHEY_TRIPLEX,
                0.5,
                (255, 0, 0),
            )
            cv2.putText(
                frame,
                f"{int(detection.confidence * 100)}%",
                (bbox[0] + 10, bbox[1] + 40),
                cv2.FONT_HERSHEY_TRIPLEX,
                0.5,
                (255, 0, 0),
            )
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)

        if not self.depth_flag:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Output the frame
        return frame

    def stop(self):
        print("Pipeline exited.")
        del self.pipeline
        super().stop()


def start_pipeline(pipeline: dai.Pipeline, options):
    depth_flag = options.camera_type == "depth"
    platform = pipeline.getDefaultDevice().getPlatformAsString()

    if platform == "RVC4":
        fps = 30
    else:
        fps = 15
    print("Creating pipeline...")

    # The host node architecture is not preferred here as the host node runs in a loop and
    #  we only want to get from the queues when pinged from the server in this example
    nn_q = None
    label_map = None
    if depth_flag:
        depth = pipeline.create(dai.node.Depth)
        depth.build(
            dai.node.Depth.Algorithm.AUTO,
            fps=fps,
            size=(options.width, options.height),
        )

        preview_q = depth.depth.createOutputQueue(blocking=False, maxSize=4)

    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            (options.width, options.height), dai.ImgFrame.Type.NV12, fps=fps
        )

        if options.nn:
            model_description = dai.NNModelDescription(options.nn)
            model_description.platform = platform
            nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

            manip = pipeline.create(dai.node.ImageManip)
            manip.initialConfig.setOutputSize(
                nn_archive.getInputWidth(),
                nn_archive.getInputHeight(),
                dai.ImageManipConfig.ResizeMode.STRETCH,
            )
            manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p)
            manip.setMaxOutputFrameSize(
                nn_archive.getInputWidth() * nn_archive.getInputHeight() * 3
            )
            if platform == "RVC4":
                manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
            cam_out.link(manip.inputImage)

            nn = pipeline.create(ParsingNeuralNetwork).build(manip.out, nn_archive)
            nn.input.setBlocking(False)
            label_map = nn_archive.getConfigV1().model.heads[0].metadata.classes
            nn_q = nn.out.createOutputQueue(blocking=False, maxSize=4)
        preview_q = cam_out.createOutputQueue(blocking=False, maxSize=4)

    print("Pipeline created.")
    return preview_q, nn_q, label_map


def frameNorm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)


def colorize_depth(frame_depth: np.ndarray) -> np.ndarray:
    invalid_mask = frame_depth == 0
    valid_depth = frame_depth[~invalid_mask]
    if valid_depth.size == 0:
        return np.zeros((*frame_depth.shape, 3), dtype=np.uint8)

    min_depth = np.percentile(valid_depth, 3)
    max_depth = np.percentile(valid_depth, 95)
    if min_depth <= 0 or max_depth <= min_depth:
        return np.zeros((*frame_depth.shape, 3), dtype=np.uint8)

    log_min_depth = np.log(min_depth)
    log_max_depth = np.log(max_depth)
    log_depth = np.full(frame_depth.shape, log_min_depth, dtype=np.float32)
    np.log(frame_depth, out=log_depth, where=~invalid_mask)
    np.nan_to_num(log_depth, copy=False, nan=log_min_depth)
    log_depth = np.clip(log_depth, log_min_depth, log_max_depth)

    depth_frame = np.interp(log_depth, (log_min_depth, log_max_depth), (0, 255))
    depth_frame = np.nan_to_num(depth_frame).astype(np.uint8)
    depth_color = cv2.applyColorMap(depth_frame, cv2.COLORMAP_JET)
    depth_color[invalid_mask] = 0
    return depth_color
