# AGENTS.md

## Summary

Standalone RVC4 starting point for visual decision-model apps: d3-lite applies VLM knowledge to user-defined image questions and returns validated, typed decisions with probabilities. YOLO-E supplies detection crops as the example input; the frontend configures classes, capture timing, and up to four Yes/No, choice, or score questions.

## Use This Example When

- You need VLM-informed, type-safe decisions for visual questions that fit a
  Yes/No, choice, or ordered-score answer contract.
- You want a reusable decision-model question/result path with object crops;
  YOLO-E is the included example source and can be replaced.
- You need a bounded scheduler that remains responsive when objects exceed decision throughput.

## Do Not Use This Example When

- You need generated prose, calibrated accuracy, or durable storage.
- You need RVC2, host/peripheral execution, or a guarantee that every detection
  receives a decision at every interval.

## Quick Facts

- `Category:` `apps/visual-decision-model`
- `Shape:` `frontend`
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Runs on:` RVC4 standalone only
- `Input:` camera at 1920 × 1080 and 640 × 640 letterbox, up to 16 text classes (default `person`), confidence/IoU, 0.5–30 s capture interval, one to four typed questions
- `Output:` validated Yes/No, choice, or score decisions with probabilities;
  H.264 `Video`, aligned boxes and masks in `Annotations`, track status, and a
  20-entry source/crop log
- `Models:` Zoo YOLO-E v8 L FP16 on SNPE/DSP; d3-lite Q8_0 and matching vision projector through llama-server/Hexagon HTP0

## Read First

- [README.md](README.md): user workflow and limits.
- [oakapp.toml](oakapp.toml): base image, model preparation, Hexagon devices and frontend build.
- [backend/src/main.py](backend/src/main.py): pipeline, observation and overlay nodes, services, state, and scheduling.
- [backend/src/detector/nn_detection_node.py](backend/src/detector/nn_detection_node.py): Zoo YOLO-E, SNPE backend, parser, and detection outputs.
- [backend/src/scheduler.py](backend/src/scheduler.py): fair selection and crop bounds.
- [backend/src/decision.py](backend/src/decision.py): native question and answer contract.
- [backend/src/images.py](backend/src/images.py): source and crop JPEG preparation.
- [backend/src/models.py](backend/src/models.py): pinned model/projector downloads and checksums.
- [backend/src/runtime.py](backend/src/runtime.py): llama-server lifecycle and `/v1/systemone` request.
- [frontend/src/App.tsx](frontend/src/App.tsx): service polling, live preview and state updates.
- [frontend/src/SettingsPanel.tsx](frontend/src/SettingsPanel.tsx): detection and decision controls.
- [frontend/src/DecisionLog.tsx](frontend/src/DecisionLog.tsx): source/crop inference history.

## Architecture

- The camera emits undistorted 640 × 640 letterboxed BGR at 10 FPS for Zoo
  YOLO-E and ObjectTracker, plus undistorted 1920 × 1080 NV12 at 10 FPS for
  H.264 `Video` and crops.
  Encoder and detector inputs drop stale frames instead of blocking the camera.
- YOLO-E runs through DepthAI's SNPE/DSP backend. The text encoder uses ONNX
  Runtime's CPU provider when classes change; its embeddings feed YOLO-E.
  Parser confidence and IoU update without rebuilding the pipeline.
- ObjectTracker uses short-term imageless matching and unique IDs.
  `ObservationNode` pairs tracklets with their 1080p frame and maps their boxes
  with DepthAI transformation metadata. It retains only an interval-selected
  frame and observations; pixel conversion runs later in the worker.
- DepthAI `Align` maps detection boxes and embedded segmentation masks to the
  paired 1080p video before publishing `Annotations`. Decision scheduling
  uses tracker IDs and boxes from the separate observation path.
- One background worker chooses unseen or least recently evaluated objects
  from the latest capture. It sends one crop with all configured questions to
  llama-server's loopback `/v1/systemone` endpoint. A newer capture replaces
  pending work and ends remaining work from the older capture.
- `Decision State`, `Detection Config`, and `Decision Config` services connect
  the backend to the frontend. State polling transfers history images only on
  initial load or for new entries. Class and question drafts require Apply;
  confidence, IoU, and interval sliders debounce automatically.

## Modification Guide

- `Safe to change:` titles, explanatory text, question defaults, frontend
  layout, and supported slider defaults within backend validation ranges.
- `Requires care:` camera outputs, letterboxing, transformation mapping,
  detection parser settings, crop sizing, question contracts, and model flags.
- `Likely to break if changed blindly:` frame/detection pairing, ObjectTracker
  IDs, the latest-capture scheduler, generation-based pause invalidation,
  RemoteConnection service payloads, or Hexagon runtime mounts.

## Common Adaptations

- `To change the default use case:` edit `DEFAULT_QUESTIONS` and default
  classes in [backend/src/main.py](backend/src/main.py), then keep frontend
  initial drafts and examples in sync.
- `To use another visual input source:` replace the YOLO-E detection and
  observation path while preserving the paired source image, exact submitted
  crop, and typed question/response contract. The decision worker and parser
  can then remain the core of the new application.
- `To adjust detection:` edit [backend/src/detector/nn_detection_node.py](backend/src/detector/nn_detection_node.py)
  for model/backend changes; update the parser/controller and frontend controls
  together for new thresholds or prompt modes.
- `To replace d3-lite:` update the pinned model/projector pair and checksums in
  [backend/src/models.py](backend/src/models.py), then verify the base image,
  llama-server flags in [backend/src/runtime.py](backend/src/runtime.py), and
  native response parsing in [backend/src/decision.py](backend/src/decision.py).
- `To change crop or log behavior:` update [backend/src/images.py](backend/src/images.py),
  [backend/src/main.py](backend/src/main.py), and the corresponding frontend
  types/rendering; preserve the exact submitted crop in history.
- `To add a frontend control:` update [frontend/src/SettingsPanel.tsx](frontend/src/SettingsPanel.tsx)
  and the service handling in [frontend/src/App.tsx](frontend/src/App.tsx), with
  backend validation and state fields in [backend/src/main.py](backend/src/main.py).

## Constraints

- Keep each source frame paired with its detections or tracklets. Never crop a
  box from a later frame. Remap detector and tracker boxes with the actual
  1080p frame transformation; do not assume simple scaling from 640 square.
- Keep the decision JPEG at most 448 pixels on its longest edge without
  stretching its aspect ratio. The marked source image remains 1080p.
- Keep one d3 request in flight. Capture interval is best effort when
  inference runs longer; no model request or image conversion may block the
  encoded stream or create an unbounded queue.
- Pause, class edits, and decision-setting changes invalidate pending work.
  An in-flight HTTP request may finish, but its stale result must not enter
  history. Class edits clear tracks; question edits clear current per-track
  answers while old history keeps its submitted questions.
- Keep server-side validation for 1–16 unique classes, 0–1 confidence/IoU,
  0.5–30 s capture intervals, and 1–4 questions with valid answer options.
  Native question types are `noul`, `choice`, and `score`.
- History holds 20 entries in memory. d3 probabilities are model outputs,
  not calibrated accuracy. No external inference service is used.

## Non-Obvious Repo Conventions

- The base image tag in [oakapp.toml](oakapp.toml) must exist. It provides
  llama.cpp; the app also needs the read-only `/opt/luxonis/npu-runtime` mount
  and FastRPC devices. The model/projector request HTP0, but inspect
  llama-server logs for actual operator placement.
- d3-lite weights and projector are downloaded and SHA-256 checked during
  `prepare_container`. Zoo YOLO-E and text prompt assets may need network or
  cache access at first start. Keep the pinned descriptor, prompt encoder,
  and model assets consistent when changing versions.
- `Video` is encoded H.264; `Annotations` carries aligned detections and masks.
  The browser renders both. The frontend never calls llama-server directly.
- `Decision State` uses a history revision so large source/crop images are
  sent only on initial load or for new entries. Service callbacks must keep
  accepting the expected JSON payloads when frontend controls change.
- `npm run dev` builds and serves the frontend bundle; restart it after edits.
  Use `?ws_url=ws://<device-ip>:8765` for local frontend development.
- Use Google-style docstrings for important backend behavior and short
  comments where frame ownership, concurrency, or transformation is subtle.

## Related Examples

- [data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): YOLO-E prompt controls and tracking.
- [llamacpp-vlm](https://github.com/luxonis/oak-examples/tree/main/apps/llamacpp-vlm): standalone llama.cpp frontend pattern.

## Validation

- `Run:` `oakctl app run . -d <device-ip> --detach`
- `Success looks like:` live `Video` and `Annotations` continue during
  decisions; boxes and segmentation masks align on 1080p video; tracked
  objects produce source/crop logs with the exact d3 input and answers; class,
  threshold, question, and interval controls work; no new prediction appears
  after pause.
- `Checks:` compile the backend source, run frontend lint/build, validate
  repository AGENTS/index docs, then inspect live topics and the browser UI.
  This example currently has no dedicated backend test directory.
- `Common failure meaning:` model build failures may indicate unavailable
  base image or downloads; startup failures may indicate missing Hexagon
  mounts/devices or unavailable Zoo/prompt assets; shifted overlays indicate
  a missing detection-to-video alignment or inconsistent camera undistortion;
  stale log entries after pause indicate a generation-invalidation regression.
- `Validation status:` validated through RVC4 standalone execution and
  frontend inspection. Holistic recording/replay remains pending for this
  topology.
