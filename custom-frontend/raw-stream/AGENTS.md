# AGENTS.md

## Summary

This is the smallest custom frontend/backend example in the repository. It is the best reference when you need a browser UI, a live DepthAI stream, and a simple request/response service between frontend and backend without bringing in the heavier WebRTC-based standalone app stack.

## Use This Example When

- You need a minimal custom frontend with live stream display.
- You need two-way communication between frontend code and backend Python code.
- You want a local host/peripheral custom UI example before moving to a more complex standalone app.
- You need a small baseline for integrating `@luxonis/depthai-viewer-common`.

## Do Not Use This Example When

- You need remote access, HTTPS, or WebRTC as the primary delivery path.
- You need encoded streaming, multi-stage NN inference, or richer UI state management.
- You need a ROS, C++, stereo, or multi-device reference.
- You need a polished standalone frontend example with model switching and interactive prompting.

## Quick Facts

- `Category:` `custom-frontend/raw-stream`
- `Shape:` `frontend`
- `Primary task:` minimal custom frontend with backend messaging
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` peripheral mode on host; RVC4 standalone packaging also exists
- `Requires:` a Luxonis device; built frontend assets; `OAKAPP_STATIC_FRONTEND_PATH` in peripheral mode
- `Input:` RGB camera stream and text messages from the frontend
- `Output:` one raw stream topic plus a simple backend service response
- `Models:` none
- `Visualizer / UI:` custom browser frontend served by [frontend_server.py](frontend_server.py)

## Read First

- [main.py](main.py): backend pipeline, frontend server startup, and registered service
- [frontend/src/App.tsx](frontend/src/App.tsx): stream rendering and UI shell
- [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx): frontend-to-backend service call
- [frontend/src/main.tsx](frontend/src/main.tsx): `DepthAIContext` wiring and browser router setup
- [frontend_server.py](frontend_server.py): local HTTP server used in peripheral mode
- [oakapp.toml](oakapp.toml): standalone static frontend build and backend entrypoint
- [utils/arguments.py](utils/arguments.py): backend CLI options

## Architecture

- Peripheral mode uses a local Python HTTP server to serve prebuilt frontend files.
- The backend creates a `dai.Device`, a `dai.RemoteConnection` with `serveFrontend=False`, and a minimal camera pipeline.
- The backend publishes a single `Raw Stream` topic.
- The backend also registers a named service that accepts a message and returns a simple JSON response.
- The frontend connects through `DepthAIContext`, renders the stream view, and posts messages back to the backend service.
- Standalone mode uses [oakapp.toml](oakapp.toml) to build and bundle the static frontend.

## Data Flow

- `Camera -> Raw Stream topic -> frontend stream viewer`
- `Frontend text input -> Message Service -> backend print + JSON response`
- `Static frontend files -> local HTTP server or standalone static frontend bundle -> browser`

## Modification Guide

- `Safe to change:` frontend layout, text labels, service payload format, topic names, port/IP defaults
- `Requires care:` service naming across backend and frontend, static frontend path handling, standalone build steps, stream topic names expected by the frontend viewer
- `Likely to break if changed blindly:` changing how the frontend is served, removing `OAKAPP_STATIC_FRONTEND_PATH` handling in peripheral mode, renaming the backend service in only one place

## Common Adaptations

- `To add a new frontend control:` extend [frontend/src/App.tsx](frontend/src/App.tsx) or [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx), then add a matching backend service or config handler in [main.py](main.py)
- `To replace the raw stream with NN output:` keep the frontend/server structure and change only the pipeline and published topics in [main.py](main.py)
- `To move toward a richer standalone app:` keep the frontend/backend split from this example, then compare against [../open-vocabulary-object-detection](../open-vocabulary-object-detection/)
- `To reuse only the frontend shell:` keep [frontend/src/main.tsx](frontend/src/main.tsx), [frontend/src/App.tsx](frontend/src/App.tsx), and the static build path from [oakapp.toml](oakapp.toml)

## Constraints

- Peripheral mode depends on `OAKAPP_STATIC_FRONTEND_PATH` pointing at built frontend assets.
- This example uses its own HTTP server instead of relying on `dai.RemoteConnection` to serve the frontend.
- The pipeline is intentionally minimal and does not demonstrate encoded streaming or advanced backend state management.
- Standalone packaging exists, but the stronger production-shaped standalone frontend reference is still [../open-vocabulary-object-detection](../open-vocabulary-object-detection/).
- The `--fps-limit` argument exists in [utils/arguments.py](utils/arguments.py), but [main.py](main.py) currently requests output with `fps=30 or args.fps_limit`, so the runtime does not actually honor the CLI FPS value as written.

## Non-Obvious Repo Conventions

- [oakapp.toml](oakapp.toml) handles both backend startup and static frontend build/bundling for standalone mode.
- Backend/frontend service names must stay aligned across [main.py](main.py), [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx), and context/service wiring in [frontend/src/main.tsx](frontend/src/main.tsx).
- In peripheral mode, frontend serving is separate from `dai.RemoteConnection`; do not assume the default Visualizer frontend is used here.

## Related Examples

- [../open-vocabulary-object-detection](../open-vocabulary-object-detection/): use this when you need a richer standalone frontend/backend app with WebRTC and model controls
- [../../tutorials/camera-demo](../../tutorials/camera-demo/): use this when you only need a minimal camera/Visualizer pipeline and no custom frontend
- [../../apps/default-app](../../apps/default-app/): use this when you need a packaged baseline app but not a custom UI
- [../../integrations/roboflow-workflow](../../integrations/roboflow-workflow/): use this when you want another frontend/backend pattern with an external inference integration

## Validation

- `Run:` build the frontend, set `OAKAPP_STATIC_FRONTEND_PATH` to `frontend/dist`, then run `python3 main.py`
- `Success looks like:` the terminal prints the served URL, the browser shows a live stream, and clicking `Send` triggers a backend response
- `Common failure meaning:` missing built frontend assets, missing `OAKAPP_STATIC_FRONTEND_PATH`, or backend/frontend service naming drift
