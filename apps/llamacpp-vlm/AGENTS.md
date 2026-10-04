# AGENTS.md

## Summary

Standalone RVC4 llama.cpp VLM example using Qwen3.5-0.8B for visual question answering with a 1080p live preview, full-frame or snapshot-region input, streamed answers, and first/last-token timing. Uses the llama.cpp base image and Luxonis frontend components.

## Use This Example When

- Demonstrating llama.cpp VLM inference on OAK4 with user-supplied prompts.
- Selecting a precise region from a frozen camera snapshot.

## Do Not Use This Example When

- Targeting RVC2 or host/peripheral execution.
- Needing continuous per-frame inference or multi-turn model conversations.

## Quick Facts

- `Category:` `apps/llamacpp-vlm`
- `Shape:` `frontend`
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Runs on:` RVC4 standalone only
- `Input:` 1920 × 1080 color camera at 20 FPS, prompt, optional normalized region, output-token limit, temperature
- `Output:` H264 Video topic, streamed answer, submitted image, first/last-token milliseconds, three-request history
- `Models:` Qwen3.5-0.8B Q4_0 and F16 projector; pinned Apache-2.0 assets

## Read First

- [backend/src/constants/config.yaml](backend/src/constants/config.yaml): startup configuration and frontend defaults.
- [backend/src/constants/__init__.py](backend/src/constants/__init__.py): YAML loading and setting validation.
- [backend/src/main.py](backend/src/main.py): VlmApp, pipeline, snapshot ownership, services, inference worker.
- [backend/src/runtime.py](backend/src/runtime.py): llama-server lifecycle and SSE timing.
- [backend/src/images.py](backend/src/images.py): ROI validation and aspect-preserving resize.
- [backend/src/models.py](backend/src/models.py): build-time model download and verification.
- [frontend/src/App.tsx](frontend/src/App.tsx): Luxonis UI, snapshot selection, and response polling.
- [frontend/src/services.ts](frontend/src/services.ts): service request/response handling.

## Architecture

- Camera NV12 output feeds the H264 Video topic and a nonblocking, one-frame queue. The capture worker retains the latest frame as an OpenCV BGR image.
- `Qwen Snapshot` retains a full-resolution frame copy and returns its JPEG preview and ID. At most four snapshots are retained; a fifth evicts the oldest. Region submissions reject snapshots older than five minutes, without a timed deletion task.
- The frontend sends normalized region coordinates and the snapshot ID, never a browser screenshot. The backend crops that saved frame before resizing. Full-frame requests use the latest frame; capture and full-frame submissions reject frames older than three seconds.
- Image preparation preserves aspect ratio and only downsizes, using `image.max_edge` (default 448). The history image is the JPEG sent to llama-server, before its internal vision preprocessing.
- `Qwen Submit` validates the prompt, output-token limit (1–256), temperature (0–1), and region, then launches one inference worker. A second request is rejected while that worker is preparing or running.
- `Qwen State` returns model readiness, generation defaults, the current job, and up to three requests newest first. History includes live answers and errors, is shared across connected clients, survives frontend reloads, and clears on app restart. It is not sent as model conversation context.
- The frontend polls state every 250 ms after each response. `Runtime` streams from llama-server's loopback-only OpenAI-compatible endpoint at `http://127.0.0.1:8081`; the frontend uses RemoteConnection services.
- Weights are downloaded and SHA-256 verified during `prepare_container`, then stored at `/opt/qwen-models` inside the app image. They survive restarts as image files; there is no external model mount, runtime download, or separately managed model cache. Frames and history stay in memory; app logs go to stdout.

## Modification Guide

- `Safe to change:` frontend labels, prompt defaults, layout, and generation defaults within the supported YAML ranges
- `Requires care:` image sizing, normalized region coordinates, model/projector pairing, llama-server flags, and token-timing semantics
- `Likely to break if changed blindly:` snapshot ownership, backend/frontend service contracts, worker shutdown and shared-state locking, or Hexagon runtime mounts and device access

## Common Adaptations

- `To change image size or generation defaults:` edit [backend/src/constants/config.yaml](backend/src/constants/config.yaml). Defaults are max edge 448, 128 output tokens, and temperature 0.0; redeploy after changing startup settings.
- `To tune llama-server:` start with the runtime settings in [backend/src/constants/config.yaml](backend/src/constants/config.yaml) and their command-line mapping in [backend/src/runtime.py](backend/src/runtime.py).
- `To replace the model:` update the pinned model/projector files and checksums in [backend/src/models.py](backend/src/models.py), then verify compatibility with the base image and request format in [backend/src/runtime.py](backend/src/runtime.py).
- `To change camera or region handling:` update [backend/src/main.py](backend/src/main.py) and [backend/src/images.py](backend/src/images.py), keeping selection coordinates in [frontend/src/App.tsx](frontend/src/App.tsx) consistent with the saved frame.
- `To add frontend controls:` update [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/services.ts](frontend/src/services.ts), and the corresponding backend validation and request handling together.

## Constraints

- The base tag in `oakapp.toml` must be available. Use its llama.cpp runtime and the required read-only OS mount at `/opt/luxonis/npu-runtime`; do not copy runtime libraries or weights from another device app.
- Hexagon HTP0 is requested for decoder and projector. Unsupported individual operations may run on CPU; do not silently switch the entire backend to CPU.
- Timings start immediately before the model HTTP request and stop at first/last nonempty content events, not browser receipt or SSE completion.
- Services must stay responsive while inference runs; never execute generation in a service callback.
- The input preview and region must refer to the same immutable snapshot; never crop a newer frame using an old selection.
- Keep server-side validation: prompts must be nonempty and at most 2000 characters; normalized regions must stay inside the frame and cover at least 16 pixels in each dimension.

## Non-Obvious Repo Conventions

- The frontend uses `Qwen Snapshot`, `Qwen Submit`, and `Qwen State` services; only the backend connects to llama-server. Service callbacks must accept the request payload, including `_message` where it is intentionally unused.
- Startup settings belong under [backend/src/constants/](backend/src/constants/). Quote `"on"` and `"off"` for flash attention so YAML does not parse them as booleans. Frontend token and temperature overrides apply per request without changing the YAML; thinking is disabled in each model request.
- The main thread owns pipeline lifetime. Capture, model loading, log draining, and inference run in workers; a shared stop event signals shutdown. Application and runtime locks protect their respective shared state, and inference runs without holding them.
- `npm run dev` builds and serves the production bundle; it does not hot-reload. Use `?ws_url=ws://<device-ip>:8765` for a local frontend connected to the device, and restart the command after edits.
- Use Google-style docstrings and short comments for non-obvious behavior.

## Related Examples

- [raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): minimal Luxonis frontend/service wiring.
- [dino-tracking](https://github.com/luxonis/oak-examples/tree/main/apps/dino-tracking): interactive standalone camera UI.

## Validation

- `Run:` `oakctl app run . -d <device-ip> --detach`
- `Success looks like:` the frontend shows live video; full-frame and region requests produce answers with matching input thumbnails and token timings; logs confirm Hexagon placement. Selected token limits and temperatures reach the model request, and four submissions leave only the newest three in history, including after a frontend reload.
- `Common failure meaning:` image build failures can indicate an unavailable base tag or model download/checksum failure; llama-server startup failures can indicate missing runtime mounts or device access; rejected region requests can indicate an expired snapshot; frontend service errors can indicate mismatched service names or payloads. Inspect failing to decode the H264 `Video` topic does not alone mean the stream is broken; verify it through the frontend and `Qwen Snapshot` preview.
- `Validation status:` validated through standalone device execution; holistic recording/replay is pending.
