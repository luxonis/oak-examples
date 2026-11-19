# AGENTS.md

## Summary

This is the repository reference for headless, boot-time multi-camera recording on an OAK4-FFC. It records every connected camera to timestamped H.264 Matroska files in persistent app storage, including cameras beyond the three RVC4 ISP streams.

## Use This Example When

- You need an OAK App that starts recording on boot with no viewer, frontend, or network connection.
- You need to record more cameras than RVC4 has ISP streams for, using raw outputs plus software conversion.
- You need persistent recordings in `OAKAGENT_STORAGE_SHARED` with quota and free-space protection.
- You need a host tool that lists, downloads, or deletes recordings through `oakctl app exec`.

## Do Not Use This Example When

- You need a live preview or the DepthAI Visualizer; this app publishes no topics.
- You need a single-camera recording reference; use `streaming/on-device-encoding`.
- You need network streaming (RTSP, WebRTC, MJPEG) rather than local files.
- You need neural inference on the recorded streams.

## Quick Facts

- `Category:` `apps/ffc-multi-camera-recorder`
- `Shape:` `script+standalone`
- `Primary task:` record every connected camera to H.264 `.mkv` files on boot
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml), started through [backend-run.sh](backend-run.sh) under `runsvdir`
- `Frontend:` none
- `Runs on:` RVC4 standalone (primary) and RVC4 peripheral; RVC2 is untested
- `Requires:` any connected cameras; raw-only cameras (fourth and later on RVC4) must be monochrome RAW10 sensors
- `Input:` all sockets from `Device.getConnectedCameraFeatures()`, sorted by socket name
- `Output:` one `<UTC stamp>[_offline]_cam<x>.mkv` per socket in `--output-dir`
- `Models:` none
- `Visualizer / UI:` none; progress goes to stdout
- `Used in:` the Underwater 360° Camera with OAK 4 FFC project (five OV9282 cameras); see [README.md](README.md) for the video, blog post, and docs links

## Read First

- [main.py](main.py): camera discovery, ISP versus raw branching, recording loop, storage limits, offline clock handling
- [utils/image_quality.py](utils/image_quality.py): RAW10 unpacking, tone mapping, startup exposure calibration, ISP brightness reference
- [oakapp.toml](oakapp.toml) and [backend-run.sh](backend-run.sh): custom runit entrypoint
- [retrieve.py](retrieve.py): host-side session listing, download, and deletion
- [tests/test_image_quality.py](tests/test_image_quality.py): hardware-free tests for the raw path

## Architecture

- The first three sockets (`MAX_ISP_STREAMS_RVC4`) use `Camera.requestOutput(NV12)` straight into a `VideoEncoder` (H.264 Main), capped at 1920x1080.
- Remaining sockets on RVC4 use `camera.raw`; `RawImageProcessor` converts RAW10 to NV12 on the host side of the pipeline (device CPU in standalone) and sends it back through `encoder.input.createInputQueue()`.
- When raw cameras exist, each ISP camera also emits a 320x200 2 FPS preview. `BrightnessReference` turns these into a smoothed luma target for raw exposure calibration.
- Raw exposure is calibrated for `--raw-exposure-settle-seconds`, then locked until restart. Exposure is preferred; digital gain (max 8x) is applied in the tone LUT.
- `H264Writer` muxes encoded packets into Matroska with PyAV using microsecond camera timestamps; no re-encoding.
- The main loop drains encoded queues before feeding raw frames, fsyncs every 5 s, and stops when the quota or free-space reserve is reached.

## Data Flow

- `CAM_A..CAM_C -> NV12 -> VideoEncoder -> H264Writer -> .mkv`
- `CAM_D.. -> RAW10 -> RawImageProcessor -> NV12 -> VideoEncoder -> H264Writer -> .mkv`
- `CAM_A..CAM_C -> 320x200 preview -> BrightnessReference -> raw exposure target -> CameraControl`

## Modification Guide

- `Safe to change:` default FPS, quota and reserve defaults, encoder profile, report and sync intervals, raw gamma and black-level defaults
- `Requires care:` the ISP stream limit, raw sensor type assumptions (OV9282 RAW10 mono), exposure controller constants, file naming (shared with `retrieve.py` regexes)
- `Likely to break if changed blindly:` switching to the default `/entrypoint.sh` (starts cloud and WebRTC services), removing exclusive file creation, changing the session filename pattern without updating `retrieve.py`

## Common Adaptations

- `To record fewer cameras:` filter `features` in [main.py](main.py) before the configuration loop.
- `To use H.265:` change the encoder profile and the `add_stream("h264")` codec in `H264Writer`.
- `To add a live preview:` add `dai.RemoteConnection` and switch back to the default `/entrypoint.sh` in [oakapp.toml](oakapp.toml).

## Constraints

- No `dai.RemoteConnection`; the app never opens the Visualizer.
- [oakapp.toml](oakapp.toml) replaces the base image entrypoint with `runsvdir -P /etc/recorder-service`, so the base image's agent services are not started.
- `python3 main.py` with no flags records indefinitely to `./recordings` in peripheral mode; use `--duration` for tests.
- Raw-only RVC4 camera paths ignore requested ISO on the tested device; brightness comes from exposure and digital gain.
- Pinned to `depthai==3.8.0` and `luxonis/oakapp-base:1.2.5`, the combination tested on hardware; the unit tests also pass on `depthai==3.11.0`.

## Non-Obvious Repo Conventions

- `retrieve.py` and `tests/` are host-only and excluded from the app package by [.oakappignore](.oakappignore).
- `retrieve.py` runs inline Python in the app container through `oakctl app exec`, so the app must be running.
- The app prints `Pipeline started.` after `pipeline.start()` for the standalone test runner.

## Related Examples

- [streaming/on-device-encoding](https://github.com/luxonis/oak-examples/tree/main/streaming/on-device-encoding): single-camera encode-and-mux reference with Visualizer preview
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): minimal preview of every connected camera
- [camera-controls/manual-camera-control](https://github.com/luxonis/oak-examples/tree/main/camera-controls/manual-camera-control): live `CameraControl` exposure tuning

## Validation

- `Unit tests:` `python3 -m unittest discover -v -s tests` from this directory; no hardware required
- `Run:` `python3 main.py --duration 10 --output-dir ./recordings`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` `Pipeline started.`, one `Recording CAM_X -> ...mkv` line per camera, periodic `Recorded ...` reports, and `.mkv` files that play in VLC
- `Common failure meaning:` a raw-only socket is not monochrome, the output directory is full or over quota, or `retrieve.py` found zero or several running apps
