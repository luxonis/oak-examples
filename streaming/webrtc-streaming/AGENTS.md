# AGENTS.md

## Summary

This is the repository reference for browser-based WebRTC streaming with runtime-selectable RGB or depth pipelines. Use it when you need a custom web UI and peer-connection setup, not a one-way media endpoint.

## Use This Example When

- You need browser delivery over WebRTC.
- You want runtime options for RGB versus depth and optional NN overlays.
- You need a custom server/client example rather than the DepthAI Visualizer.

## Do Not Use This Example When

- You need multiple concurrent independent streams.
- You need a prebuilt frontend path already checked into the repo.
- You need a standard RTSP or plain HTTP stream instead of a WebRTC app.

## Quick Facts

- `Category:` `streaming/webrtc-streaming`
- `Shape:` `web-app`
- `Primary task:` serve a browser UI that negotiates a WebRTC video stream from an OAK pipeline
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` static browser client under [client/](client/)
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging, with extra caveats around frontend assets
- `Requires:` built frontend bundle, `aiohttp`, `aiortc`, and either RGB or stereo-capable hardware depending on selected mode
- `Input:` RGB camera with optional NN model, or metric depth when `camera_type=depth`
- `Output:` WebRTC video stream and a small control datachannel
- `Models:` optional runtime-selected model slugs from the browser UI
- `Visualizer / UI:` browser on `http://<host-or-device>:8080`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [client/index.html](client/index.html)
- [client/src/client.mjs](client/src/client.mjs)
- [utils/transform.py](utils/transform.py)
- [utils/options_wrapper.py](utils/options_wrapper.py)
- [utils/datachannel.py](utils/datachannel.py)

## Architecture

- [main.py](main.py) runs an `aiohttp` app that serves the HTML shell and accepts WebRTC offers at `/offer`.
- The browser UI posts selected form options such as `camera_type`, `cam_width`, `cam_height`, and `nn_model`.
- [utils/transform.py](utils/transform.py) creates the DepthAI pipeline, exposes a `VideoStreamTrack`, and overlays detections when a model is selected for RGB mode.
- [utils/datachannel.py](utils/datachannel.py) only handles simple `PING` and `STREAM_CLOSED` messages.

## Constraints

- The current repo state does not include the built `client/build/client.js` bundle; you must build the frontend before running or packaging this example.
- [main.py](main.py) uses a single global `pipeline`, so new peer connections restart the pipeline rather than supporting multiple independent active sessions.
- Depth mode streams colorized metric depth, not RGB.
- This is a local-dev WebRTC example; HTTPS, TURN, and broader production networking concerns are outside the current implementation.

## Related Examples

- [streaming/rtsp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/rtsp-streaming): use this when you need a standard player-consumable stream instead of a browser app
- [streaming/mjpeg-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/mjpeg-streaming): use this when a simple HTTP MJPEG feed is enough
- [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): use this when you need a different custom frontend/backend app shape

## Validation

- `Build frontend:` `cd client && npm install && npm run build`
- `Run:` `python3 main.py`
- `Success looks like:` opening `http://localhost:8080` shows the controls page, `Start` produces a WebRTC video stream, and depth/RGB options change the pipeline behavior
- `Common failure meaning:` the frontend bundle was never built, the browser security model blocks local WebRTC testing, or a second client restarted the only active pipeline
