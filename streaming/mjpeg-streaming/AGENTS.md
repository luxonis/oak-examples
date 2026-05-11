# AGENTS.md

## Summary

This is the repository reference for HTTP MJPEG streaming with inline YOLOv6 overlays. Use it when you need the simplest browser-consumable stream in this category.

## Use This Example When

- You need a plain HTTP MJPEG stream.
- You want detections drawn directly into the streamed frames.
- You need camera or replay input without a separate frontend app.

## Do Not Use This Example When

- You need RTSP, WebRTC, or raw TCP instead of HTTP MJPEG.
- You need a standard DepthAI Visualizer topic workflow.
- You need a configurable server port or a control backchannel.

## Quick Facts

- `Category:` `streaming/mjpeg-streaming`
- `Shape:` `script+standalone`
- `Primary task:` serve detected frames as an MJPEG stream over HTTP
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` camera input or replay media, HTTP access to the runtime, and YOLOv6 model assets
- `Input:` live camera by default or `ReplayVideo` via `--media_path`
- `Output:` HTTP MJPEG stream on `http://<host-or-device>:8083`
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` browser or any MJPEG-capable HTTP client

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/mjpeg_streamer.py](utils/mjpeg_streamer.py)
- [utils/server.py](utils/server.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) builds a camera-or-replay input path and runs YOLOv6 through `ParsingNeuralNetwork`.
- [utils/mjpeg_streamer.py](utils/mjpeg_streamer.py) is a `HostNode` that draws detections into the passthrough frame.
- That same host node starts a threaded HTTP server and continuously updates the frame served to clients.
- [utils/server.py](utils/server.py) emits a multipart `image/jpeg` response for any GET request.

## Constraints

- The HTTP server port is fixed at `8083` in [utils/mjpeg_streamer.py](utils/mjpeg_streamer.py).
- There is no `dai.RemoteConnection` or separate topic output; the stream itself is the main interface.
- In standalone mode the MJPEG server runs on the device-side app container, so clients must connect to the device IP rather than `localhost`.

## Related Examples

- [../rtsp-streaming](../rtsp-streaming/): use this when you need a standard RTSP endpoint instead of MJPEG over HTTP
- [../webrtc-streaming](../webrtc-streaming/): use this when you need a browser-oriented interactive stream with runtime options
- [../poe-tcp-streaming](../poe-tcp-streaming/): use this when you need a custom TCP transport and a control backchannel

## Validation

- `Run:` `python3 main.py`
- `Replay mode:` `python3 main.py --media_path <VIDEO>`
- `Success looks like:` opening `http://localhost:8083` in peripheral mode shows a live MJPEG stream with YOLO detections drawn on top
- `Common failure meaning:` the HTTP port is unreachable, replay media is invalid, or the user expects a Visualizer topic instead of a standalone MJPEG endpoint
