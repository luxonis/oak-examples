# AGENTS.md

## Summary

Minimal custom frontend/backend example with a live raw camera stream and one frontend-to-backend message service. Use it as the smallest reference for wiring `@luxonis/depthai-viewer-common` to a Python backend.

## Use This Example When

- You need a browser UI around a DepthAI stream.
- You need a minimal service call from React code into Python backend code.
- You want a lightweight frontend/backend reference before using a larger WebRTC or model-control app.

## Do Not Use This Example When

- You need HTTPS, remote access, or WebRTC as the main transport.
- You need encoded streaming, neural-network inference, stereo/depth, ROS, C++, or multi-device logic.
- You need a production-shaped standalone frontend app with model switching or richer state management.

## Quick Facts

- `Entrypoint:` [main.py](main.py)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Message service:` [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) <-> [main.py](main.py)
- `Frontend server:` [frontend_server.py](frontend_server.py)
- `Standalone config:` [oakapp.toml](oakapp.toml)
- `Input:` camera stream plus text entered in the frontend
- `Output:` `Raw Stream` topic plus JSON response from `Message Service`
- `Models:` none

## Read First

- [main.py](main.py): pipeline, frontend server startup, topic registration, and service registration
- [frontend/src/App.tsx](frontend/src/App.tsx): stream rendering and UI shell
- [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx): frontend service call using `postToService`
- [frontend/src/main.tsx](frontend/src/main.tsx): `DepthAIContext` and router setup
- [oakapp.toml](oakapp.toml): static frontend build and standalone entrypoint
- [utils/arguments.py](utils/arguments.py): backend CLI options

## Architecture

- [main.py](main.py) requires `OAKAPP_STATIC_FRONTEND_PATH` and serves those built frontend assets through [frontend_server.py](frontend_server.py).
- `dai.RemoteConnection(serveFrontend=False)` exposes DepthAI topics/services while the local HTTP server handles frontend files.
- The backend publishes one topic named `Raw Stream`.
- The backend registers `Message Service`; [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) posts text to the same service name.
- [oakapp.toml](oakapp.toml) builds `frontend/dist` and starts the backend with the device IP in standalone mode.

## Modification Guide

- `Safe to change:` frontend layout, labels, service payload/response shape, stream topic name, host/port defaults
- `Requires care:` keeping service names aligned, preserving static frontend path handling, changing frontend build paths, changing topic names consumed by the UI
- `Likely to break if changed blindly:` removing `OAKAPP_STATIC_FRONTEND_PATH`, switching `serveFrontend`, renaming `Message Service` in only backend or frontend

## Common Adaptations

- `Add a frontend control:` update [frontend/src/App.tsx](frontend/src/App.tsx) or [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx), then add the matching backend service/config handling in [main.py](main.py).
- `Replace raw stream with NN output:` keep the frontend/server structure and change the pipeline plus registered topics in [main.py](main.py).
- `Reuse only the frontend shell:` keep [frontend/src/main.tsx](frontend/src/main.tsx), [frontend/src/App.tsx](frontend/src/App.tsx), and the static build path from [oakapp.toml](oakapp.toml).

## Constraints

- Peripheral mode needs built frontend assets and `OAKAPP_STATIC_FRONTEND_PATH` pointing to them.
- The frontend is served by [frontend_server.py](frontend_server.py), not by `dai.RemoteConnection`.
- This example intentionally avoids inference, encoded streaming, and advanced backend state.

## Relreated Examples

- [../open-vocabulary-object-detection](../open-vocabulary-object-detection/): richer standalone frontend/backend app with model controls
- [../../tutorials/camera-demo](../../tutorials/camera-demo/): minimal camera/Visualizer pipeline without custom frontend
- [../../apps/default-app](../../apps/default-app/): packaged baseline app without custom frontend
- [../../integrations/roboflow-workflow](../../integrations/roboflow-workflow/): another frontend/backend pattern with external inference integration

## Validation

- `Run:` build the frontend, set `OAKAPP_STATIC_FRONTEND_PATH` to `frontend/dist`, then run `python3 main.py`
- `Success looks like:` terminal prints the served URL, the browser shows a live stream, and `Send` triggers a backend response
- `Common failure meaning:` missing built frontend assets, missing `OAKAPP_STATIC_FRONTEND_PATH`, or backend/frontend service naming drift
