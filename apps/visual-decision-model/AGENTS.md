# AGENTS.md

## Summary

Standalone RVC4 decision-model example that evaluates YOLO-E detection crops with d3-lite. The Luxonis frontend configures classes, confidence, IoU, refresh target, and up to four typed questions; the default demo evaluates whether a person wears a hat.

## Use This Example When

- You need open-vocabulary detection followed by probabilistic decisions on object crops.
- You need a bounded scheduler that remains responsive when objects exceed decision throughput.

## Do Not Use This Example When

- You need generated prose, calibrated accuracy, durable storage, or RVC2 support.

## Quick Facts

- `Category:` `apps/visual-decision-model`
- `Shape:` `frontend`
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Runs on:` RVC4 standalone
- `Input:` CAM_A, text classes (person by default), detection thresholds, refresh target, one to four typed questions
- `Output:` Video and Annotations topics, per-object status, source/crop/answer log
- `Models:` Zoo YOLO-E v8 L and d3-lite Q8_0 with matching vision projector

## Read First

- [README.md](README.md): user workflow and limits.
- [backend/src/main.py](backend/src/main.py): pipeline, synchronized observations, services and scheduler loop.
- [backend/src/scheduler.py](backend/src/scheduler.py): fair selection and crop bounds.
- [backend/src/decision.py](backend/src/decision.py): native question and answer contract.
- [backend/src/runtime.py](backend/src/runtime.py): llama-server lifecycle.
- [frontend/src/App.tsx](frontend/src/App.tsx): service polling, live preview and state updates.
- [frontend/src/SettingsPanel.tsx](frontend/src/SettingsPanel.tsx): detection and decision controls.
- [frontend/src/DecisionLog.tsx](frontend/src/DecisionLog.tsx): source/crop inference history.

## Architecture

- Camera BGR output goes to the Zoo YOLO-E parser and an observation HostNode. A separate NV12 output goes to H264 Video.
- ObservationNode receives a synchronized frame and detections. A host-side IoU matcher gives boxes stable IDs and stores each box with its paired frame. The scheduler uses the latest valid observation for the chosen ID.
- YOLO-E prompt updates use CPU ONNX Runtime for text embeddings; parser confidence and IoU configs are sent at runtime.
- One scheduler thread chooses an unseen due track, then the oldest due track. It crops, JPEG encodes and sends one `/v1/systemone` request with all configured questions. No crop queue exists.
- Backend state and config services drive the frontend. History images transfer only when the history revision changes.
- The frontend keeps service polling in `App.tsx`, settings in `SettingsPanel.tsx`, and log rendering in `DecisionLog.tsx`. Shared editable question types live in `Decision.tsx`.

## Constraints

- Keep the source frame paired to its detection; do not crop a box from a later camera frame.
- Keep one d3 request in flight. Refresh is best effort and depends on observed latency with YOLO-E active.
- A class change clears live tracks. A question change invalidates current per-object decisions, while immutable history entries retain their settings.
- History holds 20 entries in memory. Model files are pinned and checksum verified at build time; no external inference service is used.
- d3 probabilities are model outputs, not calibrated accuracy. Current questions support `noul`, `choice`, and `score`.

## Related Examples

- [data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): YOLO-E prompt controls and tracking.
- [llamacpp-vlm](https://github.com/luxonis/oak-examples/tree/main/apps/llamacpp-vlm): standalone llama.cpp frontend pattern.

## Validation

- `Run:` `oakctl app run . -d <device-ip> --detach`
- `Success looks like:` live Video/Annotations, at least one real tracked detection and crop decision, exact source/crop images in history, adjustable classes/thresholds/questions, and continued YOLO-E operation while d3 is paused.
- `Checks:` backend unit tests, frontend lint/build, repository AGENTS/index checks, and live device logs/inspection.
- `Status:` live OAK4-D R9 validation passed for preview, detections, one and two question decisions, pause, and source/crop log. The OAK4-S R1 camera pipeline failed with a frame sync controller error. Holistic replay pending for standalone topology.
