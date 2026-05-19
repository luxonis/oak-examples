# AGENTS.md

## Summary

This is the best reference in the repository for live manual camera tuning through `CameraControl` messages. Use it when you need keyboard-driven exposure, focus, white-balance, denoise, and image-style controls while watching the effect immediately in the Visualizer.

## Use This Example When

- You need a compact reference for `cam.inputControl` usage.
- You want to manually tune exposure time, ISO, focus, white balance, or image style settings.
- You need a host-node example that renders a live control overlay next to the video stream.
- You want a script that works in peripheral mode and also has a standalone RVC4 packaging path.

## Do Not Use This Example When

- You need autofocus driven by detections or depth.
- You need crop control and zooming rather than sensor-parameter tuning.
- You need a custom browser frontend or a ROS app.
- You need a multi-camera or stereo-focused reference.

## Quick Facts

- `Category:` `camera-controls/manual-camera-control`
- `Shape:` `script+standalone`
- `Primary task:` keyboard-driven manual camera configuration
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` a Luxonis device with a controllable color camera on `CAM_A`
- `Input:` RGB camera frames plus keyboard input from the Visualizer window
- `Output:` `Video` and `Camera Configuration`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [main.py](main.py): camera setup, topic publication, and keyboard loop
- [utils/manual_camera_control.py](utils/manual_camera_control.py): key mappings, `CameraControl` commands, and overlay annotations
- [utils/arguments.py](utils/arguments.py): CLI surface
- [oakapp.toml](oakapp.toml): standalone packaging path
- [README.md](README.md): keyboard-control reference table

## Architecture

- The script creates one RGB camera on `CAM_A`.
- Frames are streamed to the Visualizer as `Video`.
- A custom host node, [utils/manual_camera_control.py](utils/manual_camera_control.py), receives the live frames.
- That host node publishes a `Camera Configuration` annotation overlay and sends `CameraControl` messages into the camera `inputControl` queue.
- Keyboard input is read from `visualizer.waitKey(...)` and forwarded into the host node with `handle_key_press(...)`.

## Data Flow

- `keyboard input -> ManualCameraControl host node -> camera inputControl queue`
- `CAM_A -> Video`
- `CAM_A frames -> ManualCameraControl host node -> Camera Configuration`

## Modification Guide

- `Safe to change:` hotkeys, control defaults, overlay text, default FPS, capture filename format
- `Requires care:` manual exposure limits versus FPS, lens-position bounds, enum cycling for AWB/effect/anti-banding modes, host-node key handling
- `Likely to break if changed blindly:` the selected-control state machine, the exposure/ISO pairing, or assumptions about focus-capable hardware

## Common Adaptations

- `To add another camera control:` extend [utils/manual_camera_control.py](utils/manual_camera_control.py) with a new key, state field, and annotation line
- `To change the default camera stream size:` edit the `cam.requestOutput(...)` call in [main.py](main.py)
- `To reuse only the overlay/control host node:` keep [utils/manual_camera_control.py](utils/manual_camera_control.py) and feed it another camera output plus input-control queue
- `To switch from manual to automatic focus logic:` compare against [camera-controls/depth-driven-focus](https://github.com/luxonis/oak-examples/tree/main/camera-controls/depth-driven-focus)

## Constraints

- The example assumes the color camera is on `CAM_A`.
- Keyboard interaction only works when the Visualizer window is receiving key events.
- Captured images are written to the current working directory as `capture_<WxH>_<seq>.jpg`.
- Manual exposure range is clamped based on FPS, so changing FPS changes the maximum allowed exposure time.

## Non-Obvious Repo Conventions

- Selecting a control first, then using `+` or `-`, is the main interaction pattern; `+` and `-` do nothing useful until a control is selected.
- Changing manual exposure or ISO disables autoexposure internally.
- Setting manual white balance also clears AWB lock if it was enabled.
- `Camera Configuration` is an annotation-only topic, not a second video stream.

## Related Examples

- [camera-controls/depth-driven-focus](https://github.com/luxonis/oak-examples/tree/main/camera-controls/depth-driven-focus): use this when focus should follow face depth automatically
- [camera-controls/lossless-zooming](https://github.com/luxonis/oak-examples/tree/main/camera-controls/lossless-zooming): use this when the main control problem is crop/zoom, not sensor tuning
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you need a simpler camera-streaming baseline

## Validation

- `Run:` `python3 main.py`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows `Video` plus the live `Camera Configuration` overlay, and key presses immediately change the reported settings
- `Common failure meaning:` the device lacks the expected controllable RGB camera, key events are not reaching the Visualizer window, or camera-control commands are unsupported on the target hardware
