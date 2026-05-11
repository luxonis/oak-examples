# AGENTS.md

## Summary

This is the repository reference for serving a live H265 RTSP stream from an OAK pipeline. Use it when you need a standard media endpoint that players like VLC or `ffplay` can consume.

## Use This Example When

- You need an RTSP endpoint.
- You want H265 transport from a live camera feed.
- You need a standards-based alternative to the custom TCP or MJPEG examples.

## Do Not Use This Example When

- You need browser-native delivery.
- You need replay input or per-frame inference overlays.
- You need a saved file instead of a live stream.

## Quick Facts

- `Category:` `streaming/rtsp-streaming`
- `Shape:` `script+standalone-service`
- `Primary task:` expose a live camera feed as `rtsp://.../preview`
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` GStreamer RTSP server dependencies and live `CAM_A` input
- `Input:` live camera only
- `Output:` RTSP stream on `rtsp://<host-or-device>:8554/preview` plus `Video` preview topic
- `Models:` none
- `Visualizer / UI:` RTSP client such as VLC or `ffplay`, plus DepthAI Visualizer for the preview topic

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/host_stream_output.py](utils/host_stream_output.py)
- [utils/rtsp_server.py](utils/rtsp_server.py)
- [utils/arguments.py](utils/arguments.py)
- [backend-run.sh](backend-run.sh)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) captures `CAM_A` as `640x480` NV12 and encodes it with `dai.node.VideoEncoder` using `H265_MAIN`.
- [utils/host_stream_output.py](utils/host_stream_output.py) passes encoded packets into the RTSP server implementation.
- [utils/rtsp_server.py](utils/rtsp_server.py) mounts a shared `/preview` stream through `GstRtspServer`.
- A separate raw `Video` preview is also published through `dai.RemoteConnection`.

## Constraints

- The endpoint is fixed to port `8554` and path `/preview`.
- There is no replay mode and no model/inference branch.
- The runtime depends on `gi`, `Gst`, and `GstRtspServer`, so this example is more environment-sensitive than the simpler HTTP or TCP ones.
- In standalone mode the RTSP server runs on the device-side app container, so clients must connect to the device IP.

## Related Examples

- [../mjpeg-streaming](../mjpeg-streaming/): use this when a browser-friendly HTTP stream is enough
- [../webrtc-streaming](../webrtc-streaming/): use this when you need browser delivery and runtime configuration
- [../on-device-encoding](../on-device-encoding/): use this when you need device-side encoding saved to disk rather than served live

## Validation

- `Run:` `python3 main.py`
- `Preview:` `ffplay -fflags nobuffer -fflags discardcorrupt -flags low_delay rtsp://localhost:8554/preview`
- `Success looks like:` an RTSP client can open `/preview` and the Visualizer shows the `Video` topic
- `Common failure meaning:` the GStreamer RTSP dependencies are missing, the client is pointed at the wrong host, or the user expects replay/input-selection features this example does not implement
