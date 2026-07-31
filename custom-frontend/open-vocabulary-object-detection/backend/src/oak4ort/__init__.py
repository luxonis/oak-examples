"""oak4ort: run ONNX models on the OAK4 Hexagon DSP with one function call.

    from oak4ort import qnn_session
    sess = qnn_session("model.onnx")
    out = sess.run(None, {"input": x})

Container/NPU setup (FastRPC libs, /dev/fastrpc-cdsp alias,
ADSP_LIBRARY_PATH, preinstalled onnxruntime-qnn) is provided by the
onnxruntime oakapp-base image; see README.md for the oakapp.toml
requirements.
"""

from .session import qnn_session

__version__ = "0.2.0"
__all__ = ["qnn_session", "__version__"]
