"""qnn_session(): an ort.InferenceSession on the Hexagon DSP in one call."""

import hashlib
import os
import tempfile
import warnings
from pathlib import Path

from .bootstrap import bootstrap

_EP_NAME = "QNNExecutionProvider"
_registered = False


def qnn_session(
    model_path,
    *,
    fp16=True,
    cache_context=True,
    performance_mode="burst",
    fallback_to_cpu=True,
    ep_options=None,
    session_options=None,
    verbose=False,
):
    """Create an ONNX Runtime session running on the OAK4 DSP (HTP).

    Args:
        model_path: path to a .onnx model. Inputs must have static shapes.
        fp16: run fp32 graphs in fp16 on the HTP (no-op for QDQ int8 models).
            This is what lets a plain fp32 ONNX model run with zero prep.
        cache_context: cache the compiled QNN graph (EPContext) next to the
            model so subsequent session creations skip HTP graph compilation.
        performance_mode: QNN HTP performance mode (e.g. burst, sustained_high_performance).
        fallback_to_cpu: if False, raise when the DSP is unavailable or any
            node cannot be placed on it (instead of running those on CPU).
        ep_options: extra QNN EP provider options (dict), merged last.
        session_options: pre-configured ort.SessionOptions to extend.
        verbose: enable verbose ORT logging.

    Returns:
        onnxruntime.InferenceSession
    """
    import onnxruntime as ort

    model_path = Path(model_path)
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    so = session_options or ort.SessionOptions()
    if verbose:
        so.log_severity_level = 0

    qnn_devs, why_not = _qnn_ep_devices(ort)
    if not qnn_devs:
        if not fallback_to_cpu:
            raise RuntimeError(f"QNN EP unavailable: {why_not}")
        warnings.warn(f"QNN EP unavailable ({why_not}); falling back to CPU EP")
        return ort.InferenceSession(
            str(model_path), so, providers=["CPUExecutionProvider"]
        )

    import onnxruntime_qnn

    opts = {
        "backend_path": onnxruntime_qnn.get_qnn_htp_path(),
        "htp_performance_mode": performance_mode,
        "enable_htp_fp16_precision": "1" if fp16 else "0",
    }
    if ep_options:
        opts.update({k: str(v) for k, v in ep_options.items()})

    if not fallback_to_cpu:
        so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")

    load_path = model_path
    if cache_context:
        ctx_path = _context_cache_path(model_path, opts)
        if ctx_path.is_file():
            load_path = ctx_path
        else:
            so.add_session_config_entry("ep.context_enable", "1")
            so.add_session_config_entry("ep.context_file_path", str(ctx_path))

    so.add_provider_for_devices(qnn_devs, opts)
    return ort.InferenceSession(str(load_path), sess_options=so)


def _qnn_ep_devices(ort):
    """Bootstrap + register the plugin EP; return (ep_devices, error_reason)."""
    global _registered
    status = bootstrap()
    if not status:
        return [], status.error
    try:
        import onnxruntime_qnn
    except ImportError:
        return [], "onnxruntime_qnn is not installed"
    if not _registered:
        ort.register_execution_provider_library(
            _EP_NAME, onnxruntime_qnn.get_library_path()
        )
        _registered = True
    devs = [d for d in ort.get_ep_devices() if d.ep_name == _EP_NAME]
    if not devs:
        return [], "plugin registered but no NPU EP device was enumerated"
    return devs, ""


def _context_cache_path(model_path, opts):
    """Deterministic EPContext cache location for (model, options, versions)."""
    import onnxruntime as ort
    import onnxruntime_qnn

    st = model_path.stat()
    key = "|".join(
        [
            str(model_path.resolve()),
            str(st.st_size),
            str(st.st_mtime_ns),
            ort.__version__,
            onnxruntime_qnn.__version__,
            str(sorted(opts.items())),
        ]
    )
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]

    cache_dir = os.environ.get("OAK4ORT_CACHE_DIR")
    if cache_dir:
        cache_dir = Path(cache_dir)
    elif os.access(model_path.parent, os.W_OK):
        cache_dir = model_path.parent / ".oak4ort_cache"
    else:
        cache_dir = Path(tempfile.gettempdir()) / "oak4ort_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{model_path.stem}-{digest}_ctx.onnx"
