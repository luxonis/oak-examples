# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Body-pose pipeline variant that expects Linux receiver payload as packed
# RGB888 interleaved bytes (H * W * 3).

import argparse
import logging
import os

import cuda.bindings.driver as cuda
import cupy as cp
import holoscan
from body_pose_estimation import FormatInferenceInputOp, PostprocessorOp

import hololink as hololink_module


class RgbBytesToImageOp(holoscan.core.Operator):
    """Convert packed RGB bytes into an HxWx3 tensor."""

    def __init__(self, *args, width, height, **kwargs):
        super().__init__(*args, **kwargs)
        self._width = width
        self._height = height
        self._expected_size = width * height * 3

    def setup(self, spec):
        spec.input("input")
        spec.output("output")

    def compute(self, op_input, op_output, context):
        in_message = op_input.receive("input")
        frame = cp.asarray(in_message.get(""), dtype=cp.uint8)
        if frame.size != self._expected_size:
            raise RuntimeError(
                f"Expected {self._expected_size} bytes for RGB frame, got {frame.size}"
            )
        rgb_image = frame.reshape((self._height, self._width, 3))
        op_output.emit({"": rgb_image}, "output")


class StreamControlDevice:
    """No-op stream control for externally produced Linux receiver frames."""

    def start(self):
        return

    def stop(self):
        return


class HoloscanApplication(holoscan.core.Application):
    def __init__(
        self,
        headless,
        fullscreen,
        cuda_context,
        cuda_device_ordinal,
        hololink_channel,
        stream_width,
        stream_height,
        stream_device,
        frame_limit,
        engine,
    ):
        logging.info("__init__")
        super().__init__()
        self._headless = headless
        self._fullscreen = fullscreen
        self._cuda_context = cuda_context
        self._cuda_device_ordinal = cuda_device_ordinal
        self._hololink_channel = hololink_channel
        self._stream_width = stream_width
        self._stream_height = stream_height
        self._stream_device = stream_device
        self._frame_limit = frame_limit
        self._engine = engine

    def compose(self):
        logging.info("compose")
        if self._frame_limit:
            self._count = holoscan.conditions.CountCondition(
                self,
                name="count",
                count=self._frame_limit,
            )
            condition = self._count
        else:
            self._ok = holoscan.conditions.BooleanCondition(
                self, name="ok", enable_tick=True
            )
            condition = self._ok

        frame_size = self._stream_width * self._stream_height * 3
        print(f"Frame size: {frame_size}")
        print(f"Stream width: {self._stream_width} Stream height: {self._stream_height}")

        receiver_operator = hololink_module.operators.LinuxReceiverOperator(
            self,
            condition,
            name="receiver",
            frame_size=frame_size,
            frame_context=self._cuda_context,
            hololink_channel=self._hololink_channel,
            device=self._stream_device,
        )
        rgb_unpack = RgbBytesToImageOp(
            self,
            name="rgb_unpack",
            width=self._stream_width,
            height=self._stream_height,
        )

        holoviz_args = self.kwargs("holoviz")
        holoviz_args.setdefault("width", self._stream_width)
        holoviz_args.setdefault("height", self._stream_height)

        visualizer = holoscan.operators.HolovizOp(
            self,
            name="holoviz",
            fullscreen=self._fullscreen,
            headless=self._headless,
            framebuffer_srgb=True,
            **holoviz_args,
        )

        pool = holoscan.resources.UnboundedAllocator(self)
        preprocessor_args = self.kwargs("preprocessor")
        preprocessor_args["resize_width"] = self._stream_width
        preprocessor_args["resize_height"] = self._stream_height
        preprocessor = holoscan.operators.FormatConverterOp(
            self,
            name="preprocessor",
            pool=pool,
            **preprocessor_args,
        )
        format_input = FormatInferenceInputOp(
            self,
            name="transpose",
            pool=pool,
        )
        inference = holoscan.operators.InferenceOp(
            self,
            name="inference",
            allocator=pool,
            model_path_map={
                "yolo_pose": self._engine,
            },
            **self.kwargs("inference"),
        )
        postprocessor_args = self.kwargs("postprocessor")
        postprocessor_args["image_dim"] = preprocessor_args["resize_width"]
        postprocessor = PostprocessorOp(
            self,
            name="postprocessor",
            allocator=pool,
            **postprocessor_args,
        )

        self.add_flow(receiver_operator, rgb_unpack, {("output", "input")})
        self.add_flow(rgb_unpack, visualizer, {("output", "receivers")})
        self.add_flow(rgb_unpack, preprocessor, {("output", "")})
        self.add_flow(preprocessor, format_input)
        self.add_flow(format_input, inference, {("", "receivers")})
        self.add_flow(inference, postprocessor, {("transmitter", "in")})
        self.add_flow(postprocessor, visualizer, {("out", "receivers")})

        # Not using metadata
        self.enable_metadata(False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stream-width",
        type=int,
        default=640,
        help="Input stream width in pixels",
    )
    parser.add_argument(
        "--stream-height",
        type=int,
        default=640,
        help="Input stream height in pixels",
    )
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument(
        "--fullscreen", action="store_true", help="Run in fullscreen mode"
    )
    parser.add_argument(
        "--frame-limit",
        type=int,
        default=None,
        help="Exit after receiving this many frames",
    )
    default_configuration = os.path.join(
        os.path.dirname(__file__), "body_pose_estimation.yaml"
    )
    parser.add_argument(
        "--configuration", default=default_configuration, help="Configuration file"
    )
    parser.add_argument(
        "--hololink",
        default="192.168.0.2",
        help="IP address of Hololink board",
    )
    default_engine = os.path.join(os.path.dirname(__file__), "yolov8l-pose.onnx")
    parser.add_argument(
        "--engine",
        default=default_engine,
        help="TRT engine model",
    )
    parser.add_argument(
        "--log-level",
        type=int,
        default=20,
        help="Logging level to display",
    )
    args = parser.parse_args()
    if args.stream_width <= 0 or args.stream_height <= 0:
        raise ValueError("Stream width and height must be positive integers.")

    hololink_module.logging_level(args.log_level)
    logging.info("Initializing.")

    (cu_result,) = cuda.cuInit(0)
    assert cu_result == cuda.CUresult.CUDA_SUCCESS
    cu_device_ordinal = 0
    cu_result, cu_device = cuda.cuDeviceGet(cu_device_ordinal)
    assert cu_result == cuda.CUresult.CUDA_SUCCESS
    cu_result, cu_context = cuda.cuDevicePrimaryCtxRetain(cu_device)
    assert cu_result == cuda.CUresult.CUDA_SUCCESS

    channel_metadata = hololink_module.Enumerator.find_channel(channel_ip=args.hololink)
    hololink_channel = hololink_module.DataChannel(channel_metadata)
    stream_device = StreamControlDevice()
    application = HoloscanApplication(
        args.headless,
        args.fullscreen,
        cu_context,
        cu_device_ordinal,
        hololink_channel,
        args.stream_width,
        args.stream_height,
        stream_device,
        args.frame_limit,
        args.engine,
    )
    application.config(args.configuration)

    hololink = hololink_channel.hololink()
    hololink.start()
    try:
        hololink.reset()
        application.run()
    finally:
        hololink.stop()

    (cu_result,) = cuda.cuDevicePrimaryCtxRelease(cu_device)
    assert cu_result == cuda.CUresult.CUDA_SUCCESS


if __name__ == "__main__":
    main()
