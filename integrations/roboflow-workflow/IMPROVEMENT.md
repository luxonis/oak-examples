# NPU (DSP) Inference Improvement

The workflow's ONNX models — created internally by the Roboflow `inference`
package — are rerouted from the ARM CPU to the OAK4's Hexagon DSP (NPU) via
the ONNX Runtime QNN execution provider. No changes to the `inference`
package and no model preparation (export/quantization) are required.

## Measured results

OAK4 (RVC4), Luxonis OS, 640x640 camera input, `USE_INFERENCE_MODELS=False`
(classic ONNX Runtime path of `inference`). Throughput as reported by
`AnnotationNode` (`Roboflow workflow throughput: N predictions/s`).

### Workflow `advanced-workflow` (2 models per frame)

Instance segmentation (`coco-dataset-vdnr1/2`) + keypoint detection
(`coco-pose-detection/1`) + polygon/keypoint visualization blocks.

| Mode           | Camera fps | Throughput         |
| -------------- | ---------- | ------------------ |
| CPU (`EP=cpu`) | 20         | 1.08 – 1.26 pred/s |
| DSP (`EP=dsp`) | 60         | 22.4 – 23.6 pred/s |

**~19x improvement** (~1.2 → ~23 pred/s). The ~23 pred/s is the pipeline
limit, not a camera cap: with both models on the DSP the remaining bottleneck
is the single-threaded Python side of `inference` (two pre/post passes plus
two `supervision` visualization renders per frame), not the NPU.

### Workflow `instance-seg-visualize` (1 model per frame)

| Mode           | Camera fps | Throughput                  |
| -------------- | ---------- | --------------------------- |
| CPU (`EP=cpu`) | 20         | ~2.1 pred/s                 |
| DSP (`EP=dsp`) | 20         | 20.0 pred/s (camera-capped) |

**~10x improvement**, limited by the 20 fps camera feed — the model keeps up
with every frame.

## Session creation cost

- First load of a model compiles it for the HTP: **2.5 – 3.2 s** per model.
- The compiled graph is cached next to the downloaded weights (EPContext), so
  re-creating a session for the same weights (e.g. a workflow-parameter
  restart) takes **~0.2 s**.

## How it works

- [backend/src/core/qnn_patch.py](./backend/src/core/qnn_patch.py) replaces
  the `onnxruntime.InferenceSession` module attribute (resolved at call time
  by every model class in `inference`) with a router that:
  1. fixes dynamic batch dims to 1 (the QNN EP needs fully static shapes),
  2. builds the session on the DSP through `depthai_nodes.runtime.qnn_session`
     — fp32 weights run as fp16 on the HTP,
  3. falls back to the original CPU session if anything goes wrong.
- The ONNX Runtime OakApp base image provides the QNN plugin and FastRPC
  runtime. [oakapp.toml](./oakapp.toml) passes the NPU devices and the
  scoped `/opt/luxonis/npu-runtime` package through to the container.
- `depthai-nodes==0.6.1` supplies the shared QNN runtime. The app reinstalls
  the base image's ONNX Runtime QNN versions after `inference` resolves its
  older ONNX Runtime constraint.

## Toggles

- `EP=dsp|cpu` (default `dsp`) — e.g. `oakctl app run --env EP=cpu .` to
  reproduce the CPU baseline.
- `STRICT=1` — fail instead of silently falling back to the CPU EP.

Verified in the logs by the session provider list
(`providers: ['QNNExecutionProvider', 'CPUExecutionProvider']`) and the QNN
HTP compiler output during session creation.
