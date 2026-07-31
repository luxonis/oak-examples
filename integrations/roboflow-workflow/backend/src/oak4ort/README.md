# oak4ort — run any ONNX model on the OAK4 DSP

Wraps everything needed to run ONNX Runtime inference on the OAK4's Hexagon
HTP inside a standalone OAK App:

```python
from oak4ort import qnn_session

sess = qnn_session("model.onnx")          # fp32 model -> fp16 on the DSP
out = sess.run(None, {"input": x})
```

`qnn_session()` transparently:

- bootstraps the container (FastRPC device alias, device-OS `libcdsprpc.so`
  - dependency preload, `ADSP_LIBRARY_PATH`) — see `bootstrap.py`,
- registers the `onnxruntime-qnn` plugin EP and selects the NPU device,
- caches the compiled QNN graph (EPContext) so the second session creation
  for the same model skips HTP compilation entirely,
- falls back to the CPU EP with a warning if the DSP is unavailable
  (pass `fallback_to_cpu=False` to make that an error instead).

In this app it is not used directly: `core/qnn_patch.py` routes the ONNX
sessions that the Roboflow `inference` package creates through it.

## App packaging requirements

The container needs base ORT + the QNN plugin EP (see `oakapp.toml`):

```
onnxruntime>=1.28
onnxruntime-qnn>=2.4.0
```

and the DSP passthrough block in `oakapp.toml`:

```toml
optional_devices = [
    "/dev/adsprpc-smd",
    "/dev/dma_heap/qcom,system",
    "/dev/dma_heap/system",
]
allowed_devices = [{ allow = true, access = "rwm" }]   # for the mknod alias
optional_mounts = ["/usr/lib:/host_usr_lib:ro,rbind"]  # device libcdsprpc.so
```

## Model requirements

- **Static input shapes.** The QNN EP cannot compile graphs with dynamic
  dims; `core/qnn_patch.py` fixes dynamic batch dims to 1 automatically.
- **Precision:** fp32 graphs run as fp16 on the HTP by default (no
  quantization step needed); QDQ int8 models run as-is.
- Unsupported ops fall back to the CPU EP automatically (per partition).
  Check placement with `qnn_session(..., verbose=True)`.

## Environment overrides

- `OAK4ORT_HOST_LIB_DIR` — where the device `/usr/lib` is mounted
  (default `/host_usr_lib`).
- `OAK4ORT_CACHE_DIR` — EPContext cache location (default: next to the model,
  falling back to the system temp dir).
- `ADSP_LIBRARY_PATH` — respected if already set; otherwise pointed at the
  `onnxruntime-qnn` wheel's skel directory.
