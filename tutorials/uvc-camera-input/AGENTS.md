# AGENTS.md

## Summary

This is the repository reference for injecting frames from a USB UVC camera into a DepthAI v3 pipeline. Use it when an external V4L2/OpenCV camera should behave like an `ImgFrame` source for downstream DepthAI nodes.

## Use This Example When

- You need a live `ImgFrame` source from a USB UVC camera rather than an onboard OAK camera socket.
- You want to prototype host-provided frames feeding into nodes such as `ImageManip`, `NeuralNetwork`, or `DetectionNetwork`.
- You are testing RVC4 standalone behavior where the OAK device itself can see a `/dev/video*` UVC camera.

## Do Not Use This Example When

- You need a transparent replacement for `CAM_A`, `CAM_B`, or other physical camera sockets.
- You need stereo depth from onboard synchronized mono sensors.
- You need ISP controls, calibration, or sensor metadata from the UVC camera as if it were an onboard MIPI camera.

## Quick Facts

- `Category:` `tutorials/uvc-camera-input`
- `Shape:` `script+standalone-service`
- `Primary task:` capture USB UVC frames and publish them as DepthAI `ImgFrame` messages
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` host/peripheral with a host-visible UVC camera; RVC4 standalone with an OAK-visible `/dev/video*` UVC camera
- `Requires:` a USB UVC camera visible to OpenCV
- `Input:` `--uvc-device` source, defaulting to Linux USB auto-detection
- `Output:` one DepthAI Visualizer topic after `ImageManip`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [backend-run.sh](backend-run.sh)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) defines `UvcCamera`, a `dai.node.ThreadedHostNode` with a typed `ImgFrame` output.
- The host node opens the requested UVC source through OpenCV, normalizes frames to BGR, and sends `dai.ImgFrame.Type.BGR888i` messages.
- The host-produced stream is linked into `ImageManip` to demonstrate that downstream DepthAI nodes can consume the external camera feed.
- The `ImageManip` output is published to the Visualizer as `UVC camera`.

## Data Flow

- `UVC / OpenCV VideoCapture -> UvcCamera host node -> ImageManip -> Visualizer`

## Modification Guide

- To feed a neural network, link `UvcCamera.out` or the `ImageManip` output to the NN input and configure the model's expected frame size and type.
- To target a fixed camera node, pass `--uvc-device /dev/videoN` instead of using `auto`.
- To reduce bandwidth or processing cost, set `--output-width` and `--output-height` below the capture size.

## Constraints

- Full HD BGR frames are large; downstream nodes and visualizer transport can become the bottleneck before the UVC camera does.
- Auto-detection only treats Linux video nodes with USB-backed sysfs paths as candidates, then confirms them by reading a frame.
- In peripheral mode, the UVC camera is opened on the host computer, not on the OAK device.
- In standalone mode, [oakapp.toml](oakapp.toml) exposes `/dev/video0` through `/dev/video9`; extend `optional_devices` if the target UVC node is outside that range.

## Non-Obvious Repo Conventions

- Automated example tests are marked as known-failing because this example needs an external UVC camera connected at runtime.
- The standalone config uses `runsvdir` like several Visualizer examples so `backend-run.sh` remains the only app service entrypoint.

## Related Examples

- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when onboard OAK camera sensors are the source
- [tutorials/play-encoded-stream](https://github.com/luxonis/oak-examples/tree/main/tutorials/play-encoded-stream): use this when the source is an encoded DepthAI stream
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when adding a model to a single image-like source

## Validation

- `Run:` `python3 main.py --uvc-device /dev/video2 --width 1920 --height 1080 --fps 5`
- `Standalone run:` `oakctl app run . --env UVC_DEVICE=/dev/video2`
- `Success looks like:` the Visualizer shows a `UVC camera` stream and startup logs report the selected UVC node and actual frame format
- `Common failure meaning:` no UVC camera is visible to OpenCV, the wrong `/dev/video*` node was selected, or the OAK app container was not granted access to the needed video device
