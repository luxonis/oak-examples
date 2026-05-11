# AGENTS.md

## Summary

This is the repository reference for custom bidirectional TCP streaming between an OAK pipeline and a host process. Use it when you need a simple socket protocol with camera-control messages, not a standard streaming stack.

## Use This Example When

- You need a raw TCP transport you can customize.
- You want both image delivery and host-to-device camera control messages.
- You need a reference with distinct device-side and host-side entrypoints.

## Do Not Use This Example When

- You need a standard RTSP, MJPEG, or WebRTC client flow.
- You need a browser-facing interface.
- You expect `main.py` or `dai.RemoteConnection`; this example is intentionally split into `oak.py` and `host.py`.

## Quick Facts

- `Category:` `streaming/poe-tcp-streaming`
- `Shape:` `host+device-pair`
- `Primary task:` stream MJPEG frames over TCP and send focus-control messages back
- `Entrypoints:` [oak.py](oak.py) and [host.py](host.py)
- `Standalone path:` [oakapp.toml](oakapp.toml) runs [oak.py](oak.py) in `server` mode
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging, but always with a cooperating host script for viewing/control
- `Requires:` TCP reachability on port `9876`, OpenCV on the host side, and either live camera input or replay media on the device side
- `Input:` live camera by default or `ReplayVideo` via `oak.py --media_path`
- `Output:` raw TCP video stream consumed by [host.py](host.py)
- `Models:` none
- `Visualizer / UI:` OpenCV window from [host.py](host.py)

## Read First

- [README.md](README.md)
- [oak.py](oak.py)
- [host.py](host.py)
- [utils/scripts.py](utils/scripts.py)
- [utils/oak_arguments.py](utils/oak_arguments.py)
- [utils/host_arguments.py](utils/host_arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [oak.py](oak.py) creates camera or replay input, encodes frames as MJPEG, and hands the byte stream to a `Script` node.
- [utils/scripts.py](utils/scripts.py) generates the device-side socket script for either `server` or `client` mode.
- Frames are sent with a fixed ASCII header followed by the MJPEG bytes.
- [host.py](host.py) receives the packets, decodes them with OpenCV, and sends `32`-byte focus/autofocus control messages back to the device script.

## Constraints

- The TCP port is fixed at `9876`.
- The control protocol is hardcoded around focus commands only: `AUT` for autofocus or a manual lens position value.
- In standalone mode [oakapp.toml](oakapp.toml) always starts [oak.py](oak.py) as the server, so you still need `python3 host.py client <DEVICE_IP>` to view the stream.
- There is no `dai.RemoteConnection`, no browser client, and no standards-based media transport.

## Related Examples

- [../rtsp-streaming](../rtsp-streaming/): use this when you need a standard media endpoint instead of a custom socket protocol
- [../mjpeg-streaming](../mjpeg-streaming/): use this when HTTP MJPEG is sufficient and you do not need a control backchannel
- [../on-device-encoding](../on-device-encoding/): use this when you need file recording instead of live transport

## Validation

- `Device as server:` `python3 oak.py server`
- `Host as client:` `python3 host.py client <DEVICE_IP>`
- `Success looks like:` [host.py](host.py) opens a `Color` window, frames update continuously, and `.` `,` `a` change focus behavior
- `Common failure meaning:` the wrong side started first, port `9876` is unreachable, or the user expects a standard player/client to understand this custom protocol
