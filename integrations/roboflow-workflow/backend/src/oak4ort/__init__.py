"""oak4ort: run ONNX models on the OAK4 Hexagon DSP with one function call.

from oak4ort import qnn_session
sess = qnn_session("model.onnx")
out = sess.run(None, {"input": x})
"""

from .bootstrap import bootstrap, BootstrapStatus
from .session import qnn_session

__version__ = "0.1.0"
__all__ = ["qnn_session", "bootstrap", "BootstrapStatus", "__version__"]
