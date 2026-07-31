# oak4ort_slim — run any ONNX model on the OAK4 DSP

Wraps everything needed to run ONNX Runtime inference on the OAK4's Hexagon
HTP inside a standalone OAK App:

```python
from oak4ort_slim import qnn_session

sess = qnn_session("model.onnx")          # fp32 model -> fp16 on the DSP
out = sess.run(None, {"input": x})
```

That is the whole user-facing API. `qnn_session()` transparently:

- registers the `onnxruntime-qnn` plugin EP and selects the NPU device,
- caches the compiled QNN graph (EPContext) so the second session creation
  for the same model skips HTP compilation entirely,
- falls back to the CPU EP with a warning if the DSP is unavailable
  (pass `fallback_to_cpu=False` to make that an error instead).

## Bring your own model — checklist

1. **Static input shapes.** Fix dynamic dims before shipping:
   `python -m onnxruntime.tools.make_dynamic_shape_fixed --dim_param N --dim_value 1 in.onnx out.onnx`
2. **Precision:**
   - do nothing → fp32 graph runs as **fp16** on the HTP (default),
   - or quantize to **QDQ int8** for max throughput
     (`onnxruntime.quantization`, see `scripts/quantize_model.py`).
3. Unsupported ops fall back to CPU automatically (per partition). Check
   placement with `qnn_session(..., verbose=True)`.

## App packaging requirements

Container/NPU setup (device-OS FastRPC libs, `/dev/fastrpc-cdsp` alias,
`ADSP_LIBRARY_PATH`, preinstalled `onnxruntime` + `onnxruntime-qnn`) comes
from the **onnxruntime `oakapp-base` image** (branch `onnxruntime-base` of
the `oakapp-base` repo) — no bootstrap code and no ORT pip install in the
app. `oakapp.toml` needs (copy from this app's `oakapp.toml`):

```toml
# Route through the base image entrypoint (runs the NPU setup hook):
entrypoint = ["/entrypoint.sh", "python3.12", "-u", "/app/main.py"]

# NPU device passthrough:
optional_devices = [
    "/dev/adsprpc-smd",
    "/dev/dma_heap/qcom,system",
    "/dev/dma_heap/system",
]
# oak-agent mounts optional_devices but does not add device-cgroup allow
# rules, so grant access explicitly (adsprpc-smd=496:*, dma_heap=248:*):
allowed_devices = [
    { allow = true, type = "c", major = 496, access = "rwm" },
    { allow = true, type = "c", major = 248, access = "rw" },
]

[base_image]
image_name = "oakapp-base"
image_tag = "onnxruntime"
# plus api_url pointing at a registry the device can reach
```

## Environment overrides

- `OAK4ORT_CACHE_DIR` — EPContext cache location (default: next to the model,
  falling back to the system temp dir).
- `ADSP_LIBRARY_PATH` — set to `/opt/qnn-libs` (the wheel's skel directory)
  by the base image.

## Example

`examples/minimal_dsp.py` runs any .onnx on the DSP with random inputs and
reports session-creation time (cold vs EPContext-cached) and per-inference
latency:

```bash
oakctl app run -d <DEVICE_IP> --env EP_MODES=generic .
```
