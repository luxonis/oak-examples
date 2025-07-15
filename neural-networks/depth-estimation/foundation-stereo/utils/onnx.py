import numpy as np
import onnxruntime
import os


def load_onnx_model(path):
    print("Loading ONNX model... (this may take a while)")
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = os.cpu_count()
    session = onnxruntime.InferenceSession(
        path, options, providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    print("ONNX model loaded!")
    return session


def run_onnx_inference(session, left, right):
    inputs = {
        "left": left.astype(np.float32) / 255,
        "right": right.astype(np.float32) / 255,
    }
    return session.run(None, inputs)
