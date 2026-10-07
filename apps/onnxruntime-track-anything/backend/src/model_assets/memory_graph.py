"""Static ONNX implementation of the XMem memory readout equation (no learned weights)."""

from pathlib import Path

import numpy as np
import onnx
from onnx import helper as h, numpy_helper as nh, TensorProto as T


def memory_graph(path, count):
    """Write a QNN-compatible memory-read graph for a fixed number of frames.

    Args:
        path: Destination ONNX path; unchanged graph bytes are left in place.
        count: Number of stored frames. Each contributes 720 feature locations
            from a 20 × 36 grid; the app generates variants for counts 1–5.
    """
    t = count * 720
    specs = {
        "memory_key": [t, 64],
        "memory_shrinkage": [t, 1],
        "memory_value": [512, t],
        "query_key": [64, 720],
        "query_selection": [64, 720],
    }
    nodes = []

    def op(kind, inputs, output, **kw):
        """Append a single-output ONNX node and return its output name."""
        nodes.append(h.make_node(kind, inputs, [output], **kw))
        return output

    # Expand the query-weighted squared distance without a large broadcast tensor.
    op("Mul", ["memory_key", "memory_key"], "mk2")
    op("MatMul", ["mk2", "query_selection"], "a2")
    op("Mul", ["query_key", "query_selection"], "qke")
    op("MatMul", ["memory_key", "qke"], "ab")
    op("Mul", ["ab", "two"], "ab2")
    op("Mul", ["qke", "query_key"], "b2e")
    op("ReduceSum", ["b2e", "axis0"], "b2", keepdims=1)
    op("Sub", ["ab2", "a2"], "ab_a2")
    op("Sub", ["ab_a2", "b2"], "distance")

    # Scale by memory shrinkage and sqrt(64), then normalize over stored locations.
    op("Mul", ["distance", "memory_shrinkage"], "shrunk")
    op("Div", ["shrunk", "eight"], "similarity")
    op("Softmax", ["similarity"], "affinity", axis=0)

    op("MatMul", ["memory_value", "affinity"], "readout")
    op("Reshape", ["readout", "shape"], "memory_readout")

    const = [
        nh.from_array(np.array(v, dtype=d), n)
        for n, v, d in [
            ("two", 2, np.float32),
            ("eight", 8, np.float32),
            ("axis0", [0], np.int64),
            ("shape", [1, 1, 512, 20, 36], np.int64),
        ]
    ]

    g = h.make_graph(
        nodes,
        "XMem bounded memory readout",
        [h.make_tensor_value_info(n, T.FLOAT, s) for n, s in specs.items()],
        [h.make_tensor_value_info("memory_readout", T.FLOAT, [1, 1, 512, 20, 36])],
        initializer=const,
    )
    m = h.make_model(g, opset_imports=[h.make_opsetid("", 17)])
    m.ir_version = 10
    onnx.checker.check_model(m)

    # Preserve file identity when the generated graph is already cached.
    path = Path(path)
    payload = m.SerializeToString()
    if not path.exists() or path.read_bytes() != payload:
        partial = path.with_suffix(".partial")
        partial.write_bytes(payload)
        partial.replace(path)
