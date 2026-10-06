import numpy as np
import onnxruntime as ort


class QnnSessionManager:
    """Cache strict QNN sessions and validate graph inputs and outputs."""

    def __init__(self, root, progress):
        """Initialize the session cache.

        Args:
            root: Path to the verified model release directory.
            progress: Callback accepting a human-readable loading status.
        """
        self.root, self.progress = root, progress
        self.sessions = {}

    def get(self, name):
        """Get or create a QNN session identified by ``model_family/graph_name``."""
        if name not in self.sessions:
            self.progress(f"Loading {name} on QNN…")
            folder, filename = name.split("/")
            path = str(self.root / f"{folder}-onnx-float" / f"{filename}.onnx")

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            options.log_severity_level = 3
            from depthai_nodes.runtime import onnx_qnn_session

            session = onnx_qnn_session(
                path,
                fp16=True,
                cache_context=True,
                fallback_to_cpu=False,
                runtime_fallback="raise",
                session_options=options,
            )
            self.sessions[name] = session

        return self.sessions[name]

    def unload(self, name):
        """Release an unused session while preserving its compiled cache on disk.

        Call only from the inference worker when the session is not executing.
        """
        self.sessions.pop(name, None)

    def run(self, name, **inputs):
        """Validate input shapes and run one graph on QNN.

        Args:
            name: Model identifier accepted by ``get``.
            **inputs: Named NumPy tensors matching the graph's static inputs.

        Returns:
            Output arrays in the order declared by the ONNX graph.

        Raises:
            ValueError: An input shape differs or an output is non-finite.
            KeyError: A required input is missing.
        """
        session = self.get(name)
        # A changed upstream contract must fail visibly, not silently broadcast.
        for spec in session.get_inputs():
            value = inputs[spec.name]
            if tuple(value.shape) != tuple(spec.shape):
                raise ValueError(
                    f"{name}/{spec.name}: expected {spec.shape}, got {value.shape}"
                )

        outputs = session.run(
            None,
            {k: np.ascontiguousarray(v, dtype=np.float32) for k, v in inputs.items()},
        )
        if any(not np.isfinite(x).all() for x in outputs):
            raise ValueError(f"Non-finite model output: {name}")
        return outputs
