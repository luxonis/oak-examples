#!/bin/sh
echo "Starting Backend"
# Use the classic ONNX Runtime execution path of `inference` - the default
# (torch-based `inference-models` backend) is significantly slower on ARM CPU.
export USE_INFERENCE_MODELS=False
# Keep the base provider list plain-CPU (the stock default references CUDA/
# OpenVINO/CoreML); backend/src/core/qnn_patch.py routes sessions through
# depthai-nodes' QNN runtime when the DSP is available.
export ONNXRUNTIME_EXECUTION_PROVIDERS="[CPUExecutionProvider]"
exec python3.12 /app/backend/src/main.py
