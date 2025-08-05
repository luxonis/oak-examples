import numpy as np
import onnxruntime as ort
import os
import depthai as dai
from typing import Tuple
import time
from enum import Enum

from .utility import TextHelper, letterbox_resize, postprocess_disp
from .download_utils import download_model


class InferenceState(Enum):
    START_SCREEN = "start_screen"
    RUNNING = "running"
    COMPLETED = "completed"


class FSInferer(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.onnx_session = None
        self.inference_shape = None  # (W, H) format
        self.device_stere_output = None

        self.text_helper = TextHelper()
        self.press_to_start_screen = self._create_instruction_frame(
            text="Press 'F' to start FoundationStereo inference"
        )
        self.running_screen = self._create_instruction_frame(
            "FoundationStereo inference is running..."
        )
        self.result_screen = None
        self.curr_state: InferenceState = InferenceState.START_SCREEN

        self.output = self.createOutput()

    def _create_instruction_frame(self, text: str) -> dai.ImgFrame:
        img = np.zeros((200, 600, 3), dtype=np.uint8)
        img = self.text_helper.putCenteredText(img, text)
        dai_frame = dai.ImgFrame()
        dai_frame.setCvFrame(img, dai.ImgFrame.Type.BGR888i)
        return dai_frame

    def build(
        self,
        rect_left: dai.Node.Output,
        rect_right: dai.Node.Output,
        stereo_disparity: dai.Node.Output,
        inference_shape: Tuple[int, int],
    ) -> "FSInferer":
        self.inference_shape = inference_shape
        self._create_onnx_session()
        self.link_args(rect_left, rect_right, stereo_disparity)
        return self

    def _create_onnx_session(self):
        model_path = download_model(input_shape=self.inference_shape)

        print("Loading ONNX model... (this may take a while)")
        so = ort.SessionOptions()
        so.intra_op_num_threads = os.cpu_count()
        self.onnx_session = ort.InferenceSession(
            model_path,
            so,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        print("ONNX model loaded")

    def process(
        self,
        rect_left: dai.Buffer,
        rect_right: dai.Buffer,
        stereo_disparity: dai.Buffer,
    ):
        assert isinstance(rect_left, dai.ImgFrame)
        assert isinstance(rect_right, dai.ImgFrame)
        assert isinstance(stereo_disparity, dai.ImgFrame)

        self.device_stere_output = (rect_left, rect_right, stereo_disparity)

        if self.curr_state == InferenceState.START_SCREEN:
            self.output.send(self.press_to_start_screen)
        elif self.curr_state == InferenceState.RUNNING:
            self.output.send(self.running_screen)
        elif self.curr_state == InferenceState.COMPLETED:
            if self.result_screen is None:
                raise RuntimeError("State is COMPLETED but there is no result")
            self.output.send(self.result_screen)
        else:
            raise NotImplementedError

    def infer(self):
        """Performs inference on left and right rectified streams using FoundationStereo and visualizes comparison with stereo disparity"""
        if self.device_stere_output is None:
            print("There is no left and right input pair, skipping inferece")
            return

        assert self.onnx_session is not None, "No active onnx session"
        assert self.inference_shape is not None, "Inference shape is None"

        print("Starting FoundationStereo inference")
        self.curr_state = InferenceState.RUNNING
        start_time = time.time()

        rect_left, rect_right, device_disparity = self.device_stere_output
        rect_left_img = rect_left.getCvFrame()
        rect_right_img = rect_right.getCvFrame()
        device_disparity_img = device_disparity.getCvFrame()

        input_left = self._preprocess_image(rect_left_img)
        input_right = self._preprocess_image(rect_right_img)

        inputs = {
            "left": input_left,
            "right": input_right,
        }
        outputs = self.onnx_session.run(None, inputs)
        nn_disparity = outputs[0][0, 0]
        print(
            f"FoundationStereo inference finished (took {round(time.time() - start_time, 2)}s)"
        )

        nn_out_disp = postprocess_disp(nn_disparity)
        device_out_disp = postprocess_disp(device_disparity_img)

        combined_output = self._combine_outputs(
            nn_disp=nn_out_disp, device_disp=device_out_disp
        )

        combined_output_frame = dai.ImgFrame()
        combined_output_frame.setCvFrame(combined_output, dai.ImgFrame.Type.BGR888i)

        self.result_screen = combined_output_frame
        self.curr_state = InferenceState.COMPLETED

    def _preprocess_image(self, image: np.ndarray):
        letterboxed, _, _ = letterbox_resize(image, self.inference_shape)
        out = letterboxed.transpose(2, 0, 1)[None, ...]  # NCHW
        out = out.astype(np.float32) / 255
        return out

    def _combine_outputs(self, nn_disp, device_disp):
        bar_height = 40  # Height of the label bar

        nn_resized, _, _ = letterbox_resize(nn_disp, self.inference_shape)
        dev_resized, _, _ = letterbox_resize(device_disp, self.inference_shape)

        # Black bars
        w = self.inference_shape[0]
        label_bar = np.zeros((bar_height, w, 3), dtype=np.uint8)

        label_left = self.text_helper.putCenteredText(
            label_bar.copy(), "Device Disparity"
        )
        label_right = self.text_helper.putCenteredText(
            label_bar.copy(), "FoundationStereo Disparity"
        )

        dev_with_label = np.vstack((label_left, dev_resized))
        nn_with_label = np.vstack((label_right, nn_resized))

        combined = np.hstack((dev_with_label, nn_with_label))
        return combined
