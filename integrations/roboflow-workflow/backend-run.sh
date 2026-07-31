#!/bin/sh
echo "Starting Backend"
# Use the classic ONNX Runtime execution path of `inference` - the default
# (torch-based `inference-models` backend) is significantly slower on ARM CPU.
export USE_INFERENCE_MODELS=False
exec python3.11 /app/backend/src/main.py
