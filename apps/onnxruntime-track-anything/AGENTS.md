# AGENTS.md

## Summary

Standalone RVC4 ONNX Runtime example using MobileSAM point/box selection and Track-Anything's XMem tracker for single-object video segmentation with a 720p live preview, native segmentation overlays, movement trails, and inference timing. Uses the ONNX Runtime base image.

## Use This Example When

- Demonstrating ONNX Runtime/QNN inference on OAK4 with nongenerative models.
- Selecting an object from a frozen camera snapshot and tracking its segmentation mask.

## Do Not Use This Example When

- Targeting RVC2 or host/peripheral execution.
- Requiring multi-object tracking.
- Building LLM/VLM/VLA applications; use the llama.cpp examples for those paths.

## Quick Facts

- `Category:` `apps/onnxruntime-track-anything`
- `Shape:` `frontend`
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Runs on:` RVC4 standalone only
- `Input:` 1280 × 720 color camera at 20 FPS, normalized include/exclude points or box corners
- `Output:` synchronized H264 Video topic, ImgDetections with segmentation, SegmentationMask, outline/trail ImgAnnotations, tracking rate and stage timings
- `Models:` Qualcomm AI Hub Models v0.63.0 MobileSAM and Track Anything ONNX float exports; pinned SHA-256 checksums

## Read First

- [backend/src/main.py](backend/src/main.py): pipeline, services, worker startup, and shutdown.
- [backend/src/controller.py](backend/src/controller.py): TrackingController, snapshot ownership, validation, camera history, and inference worker.
- [backend/src/publisher.py](backend/src/publisher.py): TrackingPublisher, matched video and annotation publication.
- [backend/src/annotations.py](backend/src/annotations.py): native segmentation, outline, box, and trail messages.
- [backend/src/inference/sessions.py](backend/src/inference/sessions.py): strict QNN sessions, compiled-context caching, and tensor validation.
- [backend/src/inference/mobilesam.py](backend/src/inference/mobilesam.py): frozen-frame encoding, prompt-count decoders, and mask coordinate mapping.
- [backend/src/inference/xmem.py](backend/src/inference/xmem.py): recurrent mask propagation and bounded tracking memory.
- [backend/src/model_assets/prepare.py](backend/src/model_assets/prepare.py): build-time model download, verification, and static graph preparation.
- [backend/src/model_assets/memory_graph.py](backend/src/model_assets/memory_graph.py): QNN-compatible memory matching graphs.
- [frontend/src/App.tsx](frontend/src/App.tsx): Luxonis UI, snapshot selection, overlays, and state polling.
- [frontend/src/services.ts](frontend/src/services.ts): service request/response handling.

## Architecture

- Camera NV12 output feeds a nonblocking, one-frame queue. The capture worker retains the latest frame and BGR image plus a bounded  history for tracking catch-up.
- `Track Action` captures an immutable snapshot and returns its JPEG preview and ID. Include/exclude clicks and box corners use normalized coordinates tied to that saved frame, never a browser screenshot or a newer camera frame.
- MobileSAM encodes each frozen frame once, then refines its mask with static prompt-count decoder graphs. Only the active decoder session stays resident; compiled QNN contexts remain in the container for reuse when switching back.
- `Track Action` validates selection edits and tracking commands, then queues model work for one inference worker. Snapshot IDs and epochs reject stale requests and prevent cleared or replaced jobs from publishing.
- XMem propagates the confirmed mask at 576 × 320. It retains the initial reference plus four recent memory entries, updates memory every five steps, and runs weighted squared-distance memory matching through generated QNN graphs. Catch-up skips intermediate history when inference falls behind and is bounded to 24 steps or five seconds.
- The publisher pairs every mask with its exact source camera frame before H264 encoding. Segmentation, outlines, boxes, and trails use native messages with matching metadata; they are not painted into camera pixels.
- `Track State` returns readiness, selection lifetime, tracking state, visualization options, errors, and stage timings. The frontend polls every 250 ms after each response. State is shared across connected clients and clears on app restart.
- Weights are downloaded and SHA-256 verified during `prepare_container`, with static graphs generated under `/opt/track-anything-models/v0.63.0` inside the image. Runtime verifies bundled files without downloads. Compiled QNN contexts stay at `/opt/track-anything-cache` inside the container; replacing the container can require recompilation.

## Modification Guide

- `Safe to change:` frontend labels, colors, layout, and visualization defaults
- `Requires care:` camera/model resolutions, normalized prompt coordinates, prompt labels, decoder graph assumptions, memory capacity, and timing semantics
- `Likely to break if changed blindly:` snapshot ownership, epoch checks, backend/frontend service contracts, segmentation indices and frame metadata, worker/topic shutdown, or Hexagon runtime mounts and device access

## Common Adaptations

- `To change camera or model image size:` update [backend/src/main.py](backend/src/main.py) and the relevant wrapper under [backend/src/inference/](backend/src/inference/), keeping snapshot coordinates and annotation transforms consistent.
- `To tune tracking memory:` edit [backend/src/inference/xmem.py](backend/src/inference/xmem.py) and the static memory graphs in [backend/src/model_assets/memory_graph.py](backend/src/model_assets/memory_graph.py), then verify graph parity and device memory use.
- `To replace the models:` update the release, archives, and graph preparation in [backend/src/model_assets/prepare.py](backend/src/model_assets/prepare.py), file checksums in [backend/src/model_assets/manifest.json](backend/src/model_assets/manifest.json), and the corresponding inference wrappers. Revalidate graph assumptions and rebuild the image; do not reuse incompatible QNN contexts.
- `To change selection handling:` update [backend/src/controller.py](backend/src/controller.py), [backend/src/inference/mobilesam.py](backend/src/inference/mobilesam.py), and [frontend/src/App.tsx](frontend/src/App.tsx) together, including coordinate and expiry tests.
- `To add frontend controls:` update [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/services.ts](frontend/src/services.ts), and the corresponding backend validation and request handling together.

## Constraints

- The base tag in `oakapp.toml` must be published. Use its ONNX Runtime and required read-only mount at `/opt/luxonis/npu-runtime`; do not pip-install a replacement onnxruntime wheel.
- All model inference and memory matching use strict QNN on Hexagon HTP. Unsupported execution must fail visibly; no implicit CPU fallback or provider switch.
- Services must stay responsive while inference runs; never execute model work in a service callback. Unload decoder sessions only on the inference worker and preserve their compiled contexts.
- Models and compiled contexts belong inside the app container, not `OAKAGENT_STORAGE_APP` or another external model mount. Runtime must not download missing models; require rebuilding the image.
- Selection expires after 20 seconds. Show one toast per expired snapshot, disable editing/start, and offer a fresh capture. A box replaces previous prompts and uses two of eight prompt slots. Keep camera-pane status banners removed.
- Preserve segmentation index 0 for the target and 255 for background, plus source sequence, timestamps, and transformation on annotations.
- Report device-side timings accurately: frame receipt-to-result excludes browser transport, decoding, and display latency. Keep one camera-owning pipeline on the device.

## Non-Obvious Repo Conventions

- The frontend uses `Track Action` and `Track State` services. Service callbacks must accept the request payload, including intentionally unused state payloads.
- Match the other apps: full-height Luxonis `Streams` on the left and scrolling title, description, and controls on the right, using `@luxonis/ui-components` and shared theme tokens. Narrow screens stack the panes.
- The main thread owns pipeline lifetime. Capture and inference run in workers; a shared stop event signals shutdown, and model execution runs outside the shared-state lock.
- Shutdown must join capture/inference workers, stop the pipeline, then explicitly remove RemoteConnection topics. `removeTopic` releases the GIL while joining native publisher threads; relying on the connection destructor can deadlock on Python-backed messages.

## Related Examples

- [raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): minimal Luxonis frontend/service wiring.
- [dino-tracking](https://github.com/luxonis/oak-examples/tree/main/apps/dino-tracking): segmentation proposals plus appearance matching.
- [llamacpp-vlm](https://github.com/luxonis/oak-examples/tree/main/apps/llamacpp-vlm): generative visual question answering.

## Validation

- `Run:` `oakctl app run . -d <device-ip> --detach`
- `Success looks like:` live 720p video; include/exclude/box selection produces an aligned mask; start, clear, and reselect work; mask/outline/box/trail toggles update native overlays; expiry offers a fresh capture; logs confirm QNN loading. Pressing `q` exits the backend without a topic-thread hang. Build the frontend with `npm ci && npm run build`; run `python3 -m unittest discover -s backend/tests -v` with `TRACK_MODELS` pointing to verified models for graph parity checks.
- `Common failure meaning:` image build failures can indicate an unavailable base tag or model download/checksum failure; QNN loading failures can indicate missing runtime mounts or device access; rejected selections can indicate expired or replaced snapshots; frontend service errors can indicate mismatched names or payloads.
- `Validation status:` validated through standalone device execution, frontend checks, and backend tests.
