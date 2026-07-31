"""Routes the `inference` package's ONNX sessions to the OAK4 DSP (QNN EP).

The Roboflow `inference` package builds every model session through the
`onnxruntime.InferenceSession(...)` module attribute, which is resolved at
call time. `install()` swaps that attribute for a router that:

1. copies the downloaded weights with the dynamic batch dim fixed to 1
   (the QNN EP requires fully static shapes),
2. creates the session on the DSP via `oak4ort.qnn_session()` — fp32 weights
   run as fp16 on the HTP, and the compiled graph is cached (EPContext) so
   only the first load of a given model pays HTP compilation,
3. falls back to the original CPU session if anything goes wrong.

Environment variables:
    EP:     "dsp" (default) routes sessions to the DSP, "cpu" disables the patch.
    STRICT: "1" raises instead of falling back to the CPU EP (debugging aid).
"""

import logging
import os
import threading
from pathlib import Path
from time import perf_counter

import onnxruntime

from oak4ort import bootstrap, qnn_session

# Must be set before `inference.core.env` is imported (this module is imported
# first in main.py): the stock default lists CUDA/OpenVINO/CoreML, which only
# produce warnings on RVC4 and would hide the OpenVINO-marked metadata-probe
# sessions the router needs to recognize (see `_try_qnn`).
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", "[CPUExecutionProvider]")

logger = logging.getLogger(__name__)

_real_inference_session = onnxruntime.InferenceSession
_in_router = threading.local()
_installed = False


def install() -> bool:
    """Reroutes `onnxruntime.InferenceSession` to the DSP; returns success.

    Must be called before the Roboflow pipeline loads its models. A no-op
    (returning False) with `EP=cpu` or when the DSP bootstrap fails, e.g.
    when running locally on x86 — the app then behaves exactly as before.
    """
    global _installed
    if os.environ.get("EP", "dsp").lower() != "dsp":
        logger.info("EP=%s: inference stays on the CPU EP", os.environ.get("EP"))
        return False
    status = bootstrap()
    if not status:
        if _strict():
            raise RuntimeError(f"STRICT=1 but the DSP is unavailable: {status.error}")
        logger.warning(
            "DSP unavailable (%s); inference stays on the CPU EP", status.error
        )
        return False
    if not _installed:
        onnxruntime.InferenceSession = _routed_inference_session
        _installed = True
    logger.info("DSP bootstrap OK: inference ONNX sessions will use the QNN EP")
    return True


def _strict() -> bool:
    return os.environ.get("STRICT", "0") == "1"


def _routed_inference_session(
    path_or_bytes, sess_options=None, providers=None, provider_options=None, **kwargs
):
    """Drop-in `onnxruntime.InferenceSession` replacement preferring the DSP."""
    session = None
    if not getattr(_in_router, "active", False):
        try:
            session = _try_qnn(path_or_bytes, providers)
        except Exception as e:
            if _strict():
                raise
            logger.warning(
                "QNN session for %s failed (%s); falling back to the CPU EP",
                path_or_bytes,
                e,
            )
    if session is not None:
        return session
    return _real_inference_session(
        path_or_bytes,
        sess_options=sess_options,
        providers=providers,
        provider_options=provider_options,
        **kwargs,
    )


def _try_qnn(path_or_bytes, providers):
    """QNN session for the model, or None if it should stay on the CPU."""
    if not isinstance(path_or_bytes, (str, os.PathLike)):
        return None  # in-memory model bytes: leave on the CPU
    if providers and "OpenVINOExecutionProvider" in providers:
        # inference's metadata-only probe session (load_weights=False); it
        # only reads input shapes, so an HTP compilation would be wasted.
        return None

    model_path = Path(path_or_bytes)
    static_path = _static_batch_copy(model_path)

    t0 = perf_counter()
    _in_router.active = True
    try:
        session = qnn_session(static_path, fallback_to_cpu=not _strict())
    finally:
        _in_router.active = False
    logger.info(
        "ONNX session for %s ready in %.1f s (providers: %s)",
        model_path,
        perf_counter() - t0,
        session.get_providers(),
    )
    return session


def _static_batch_copy(model_path: Path) -> Path:
    """Returns a copy of the model with dynamic batch dims fixed to 1.

    Roboflow-served weights usually keep the batch dimension dynamic, which
    the QNN EP cannot compile. Only leading (batch) dims are fixed; a dynamic
    non-batch dim makes the model ineligible for the DSP.
    """
    import onnx
    from onnxruntime.tools.onnx_model_utils import (
        fix_output_shapes,
        make_dim_param_fixed,
        make_input_shape_fixed,
    )

    model = onnx.load(str(model_path))
    graph = model.graph
    initializers = {init.name for init in graph.initializer}
    inputs = [inp for inp in graph.input if inp.name not in initializers]

    batch_params = set()
    unnamed_batch_inputs = []
    for inp in inputs:
        dims = inp.type.tensor_type.shape.dim
        for axis, dim in enumerate(dims):
            if dim.HasField("dim_value"):
                continue  # static
            if axis != 0:
                raise ValueError(
                    f"input {inp.name!r} has a dynamic non-batch dim (axis {axis})"
                )
            if dim.HasField("dim_param") and dim.dim_param:
                batch_params.add(dim.dim_param)
            else:
                unnamed_batch_inputs.append(inp)

    if not batch_params and not unnamed_batch_inputs:
        return model_path  # already fully static

    static_path = model_path.with_name(model_path.stem + ".static.onnx")
    if (
        static_path.is_file()
        and static_path.stat().st_mtime >= model_path.stat().st_mtime
    ):
        return static_path

    for param in sorted(batch_params):
        make_dim_param_fixed(graph, param, 1)
    for inp in unnamed_batch_inputs:
        shape = [1] + [d.dim_value for d in inp.type.tensor_type.shape.dim[1:]]
        make_input_shape_fixed(graph, inp.name, shape)
    fix_output_shapes(model)

    tmp_path = static_path.with_suffix(".tmp")
    onnx.save(model, str(tmp_path))
    os.replace(tmp_path, static_path)
    logger.info("fixed dynamic batch dim: %s -> %s", model_path.name, static_path.name)
    return static_path
