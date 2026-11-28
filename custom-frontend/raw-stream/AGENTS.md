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
- `Message service:` [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) \<-> [main.py](main.py)
- `Frontend server:` `depthai_nodes.runtime.serve_frontend`
- `Standalone config:` [oakapp.toml](oakapp.toml)
- `Input:` camera stream plus text entered in the frontend
- `Output:` `Raw Stream` topic plus JSON response from `Message Service`
- `Models:` none

## Read First

- [main.py](main.py): pipeline, frontend server startup, topic registration, and service registration
- [frontend/src/App.tsx](frontend/src/App.tsx): stream rendering and the side-column message card
- [frontend/src/AppShell.tsx](frontend/src/AppShell.tsx) and [frontend/src/index.css](frontend/src/index.css): shared page shell (title, connection badge, streams, side column) copied into every oak-examples custom frontend
- [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx): frontend service call using `postToService`
- [frontend/src/main.tsx](frontend/src/main.tsx): `DepthAIContext` and router setup
- [oakapp.toml](oakapp.toml): static frontend build and standalone entrypoint
- [utils/arguments.py](utils/arguments.py): backend CLI options

## Architecture

- [main.py](main.py) resolves `frontend/dist` relative to its own path and serves it through `depthai_nodes.runtime.serve_frontend`. In standalone mode it uses `OAKAPP_STATIC_FRONTEND_PATH` and `OAKAPP_STATIC_FRONTEND_PORT`; CLI directory and port options take precedence.
- `dai.RemoteConnection(serveFrontend=False)` exposes DepthAI topics/services while the local HTTP server handles frontend files. `DepthAIContext` connects directly to `ws://<page-host>:8765`, independent of the HTTP port.
- The backend publishes one topic named `Raw Stream`.
- The backend registers `Message Service`; [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx) posts text to the same service name.
- [oakapp.toml](oakapp.toml) builds `frontend/dist` and starts Python directly in the default Debian container, binding HTTP to the device IP in standalone mode.

## Modification Guide

- `Safe to change:` frontend layout, labels, service payload/response shape, stream topic name, host/port defaults
- `Requires care:` keeping service names aligned, preserving static frontend path handling, changing frontend build paths, changing topic names consumed by the UI
- `Likely to break if changed blindly:` dropping the standalone frontend path/port settings, switching `serveFrontend`, renaming `Message Service` in only backend or frontend

## Common Adaptations

- `Add a frontend control:` update [frontend/src/App.tsx](frontend/src/App.tsx) or [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx), then add the matching backend service/config handling in [main.py](main.py).
- `Replace raw stream with NN output:` keep the frontend/server structure and change the pipeline plus registered topics in [main.py](main.py).
- `Reuse only the frontend shell:` keep [frontend/src/main.tsx](frontend/src/main.tsx), [frontend/src/AppShell.tsx](frontend/src/AppShell.tsx), [frontend/src/index.css](frontend/src/index.css), [frontend/src/App.tsx](frontend/src/App.tsx), and the static build path from [oakapp.toml](oakapp.toml).
- `Add a control card:` put it in the `AppShell` children as a `Card variant="outline" intent="white"`, like the message card in [frontend/src/MessageInput.tsx](frontend/src/MessageInput.tsx).

## Constraints

- Peripheral mode supports RVC2 and RVC4 and needs built frontend assets. Standalone mode requires RVC4.
- Peripheral HTTP binds to loopback; standalone HTTP binds to the device IP. This example has no HTTPS proxy or Hub WebRTC service.
- This example intentionally avoids inference, encoded streaming, and advanced backend state.

## Related Examples

- [custom-frontend/open-vocabulary-object-detection](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/open-vocabulary-object-detection): richer standalone frontend/backend app with model controls
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): minimal camera/Visualizer pipeline without custom frontend
- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): packaged baseline app without custom frontend
- [integrations/roboflow-workflow](https://github.com/luxonis/oak-examples/tree/main/integrations/roboflow-workflow): another frontend/backend pattern with external inference integration

## Validation

- `Run:` build the frontend with `npm ci && npm run build`, then run `python3 main.py`
- `Success looks like:` terminal prints the served URL, the browser shows a live stream, and `Send` triggers a backend response
- `Common failure meaning:` missing built frontend assets, an occupied frontend port, or backend/frontend service naming drift
