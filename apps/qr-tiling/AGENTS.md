# AGENTS.md

## Summary

This is the best standalone reference for high-resolution tiled QR detection with runtime tiling control and adaptive FPS backpressure handling. Use it when you need a live UI for changing tile layout instead of a fixed tiling pipeline.

## Use This Example When

- You need QR detection over a high-resolution frame by splitting it into tiles.
- You want runtime control over rows, columns, overlap, merged regions, and optional global detection.
- You need a reference for adjusting FPS in response to pipeline load as tile count changes.
- You want a frontend/backend standalone app with service-driven configuration.

## Do Not Use This Example When

- You only need a fixed tiled QR example without a frontend.
- You need general object detection rather than QR detection and decode.
- You need a custom frontend with two-way arbitrary services unrelated to tiling.
- You need host/peripheral support instead of standalone-only RVC4 packaging.

## Quick Facts

- `Category:` `apps/qr-tiling`
- `Shape:` `frontend`
- `Primary task:` high-resolution tiled QR detection with live tiling controls
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; static frontend build; bundled QR detector; `libzbar` for decode support
- `Input:` high-resolution RGB camera frames and frontend tiling/decode controls
- `Output:` `Video` and `Visualizations`
- `Models:` [qrdet_nano.RVC4.yaml](backend/src/depthai_models/qrdet_nano.RVC4.yaml)
- `Visualizer / UI:` custom static frontend

## Read First

- [backend/src/main.py](backend/src/main.py): full tiling, decode, FPS, and service wiring
- [backend/src/tiling/tiling.py](backend/src/tiling/tiling.py): runtime tiling node
- [backend/src/tiling/tiling_config_service.py](backend/src/tiling/tiling_config_service.py): tiling update service and validation
- [backend/src/tiling/tile_grid_overlay.py](backend/src/tiling/tile_grid_overlay.py): tile grid overlay rendering
- [backend/src/fps_control/pipeline_health_monitor.py](backend/src/fps_control/pipeline_health_monitor.py): adaptive FPS logic
- [backend/src/fps_control/fps_controller.py](backend/src/fps_control/fps_controller.py): RGB pacing
- [backend/src/qr_scan/qr_decoder.py](backend/src/qr_scan/qr_decoder.py): decode stage
- [backend/src/qr_scan/qr_service.py](backend/src/qr_scan/qr_service.py): decode enable/disable service
- [backend/src/params_service.py](backend/src/params_service.py): state export to frontend
- [frontend/src/App.tsx](frontend/src/App.tsx): initial-state fetch and decode toggle
- [frontend/src/TilingControl.tsx](frontend/src/TilingControl.tsx): tiling UI
- [oakapp.toml](oakapp.toml): static frontend build and extra `libzbar` installation

## Architecture

- One RGB camera produces a high-resolution NN stream and a lower-resolution display stream.
- `FPSController` gates the frame rate for both paths.
- `Tiling` generates manip configs for tiled crops over the high-resolution image.
- `FrameCropper` extracts the tiles.
- A parsing NN runs QR detection per tile.
- Detection collections are remapped into display space, merged, filtered with NMS, and optionally decoded.
- `PipelineHealthMonitor` feeds safe FPS targets back into the controller as tile count changes.
- A tile-grid overlay is rendered onto the display stream, then encoded for frontend viewing.

## Data Flow

- `RGB high-res -> Tiling -> FrameCropper -> QR detector NN -> collected detections`
- `collected detections -> coordinate remap -> merge -> NMS -> QRDecoder -> Visualizations`
- `RGB display -> TileGridOverlay -> VideoEncoder -> Video`
- `pipeline health -> FPSController target_fps`
- `frontend services -> tiling config / decode state -> backend`

## Modification Guide

- `Safe to change:` default tiling params, overlap limits, decode toggle UI, topic names, tile-grid presentation
- `Requires care:` tile coordinate mapping, grid matrix semantics, FPS feedback behavior, display-versus-NN resolution assumptions
- `Likely to break if changed blindly:` merged-region handling, FPS recovery logic, or the contract between the frontend and `Get Current Params Service`

## Common Adaptations

- `To change default tile behavior:` edit `DEFAULT_TILING_PARAMS` in [backend/src/main.py](backend/src/main.py)
- `To change how FPS adapts:` start in [backend/src/fps_control/pipeline_health_monitor.py](backend/src/fps_control/pipeline_health_monitor.py)
- `To reuse only the tiling UI:` keep [frontend/src/TilingControl.tsx](frontend/src/TilingControl.tsx) and reimplement the backend services
- `To compare against a fixed tiling pipeline:` see [tutorials/qr-with-tiling](https://github.com/luxonis/oak-examples/tree/main/tutorials/qr-with-tiling)

## Constraints

- This example is RVC4 standalone only.
- `libzbar-dev` is installed in [oakapp.toml](oakapp.toml) because QR decoding depends on it.
- Tile count directly affects throughput, so the frontend may change FPS behavior when configuration changes.
- The frontend displays only the `Video` topic by default even though the backend also publishes `Visualizations`.

## Non-Obvious Repo Conventions

- `gridSize` is passed around as `(cols, rows)`, not `(rows, cols)`.
- Initial frontend state is restored by fetching `Get Current Params Service`, not by hardcoding frontend defaults.
- Decode enablement is a separate service from tiling configuration.
- The overlay shown in `Video` is a display stream with tile-grid rendering, not the raw NN input.

## Related Examples

- [tutorials/qr-with-tiling](https://github.com/luxonis/oak-examples/tree/main/tutorials/qr-with-tiling): use this when you want a simpler tiled QR detection reference
- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): use this when you need another service-driven standalone frontend/backend app
- [custom-frontend/open-vocabulary-object-detection](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/open-vocabulary-object-detection): use this when you want a richer frontend/backend baseline
- [apps/focused-vision](https://github.com/luxonis/oak-examples/tree/main/apps/focused-vision): use this when the tiling idea matters but the task is detail-preserving face detection instead of QR

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend loads current tiling settings, changing rows or columns updates the backend, and QR detections remain stable while FPS adjusts under higher load
- `Common failure meaning:` the static frontend was not built, `libzbar` or model assets are unavailable, or the tiling/state service contract drifted
