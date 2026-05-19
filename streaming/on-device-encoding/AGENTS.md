# AGENTS.md

## Summary

This is the repository reference for encoding video on the OAK device and muxing it directly into a container file without host-side decode or re-encode. Use it when your goal is recording efficiency rather than network streaming.

## Use This Example When

- You need encoded video written directly to a file.
- You want to compare `h264`, `h265`, and `mjpeg` device-side encoding.
- You need a minimal archival pipeline with low host processing overhead.

## Do Not Use This Example When

- You need RTSP, MJPEG, WebRTC, or TCP live streaming.
- You need replay input or a multi-camera pipeline.
- You need the host to transcode or postprocess frames before saving.

## Quick Facts

- `Category:` `streaming/on-device-encoding`
- `Shape:` `script+standalone-service`
- `Primary task:` encode live camera frames on-device and mux them into a file
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [backend-run.sh](backend-run.sh) and [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` `CAM_A`, PyAV on the runtime side, and filesystem access to the output path
- `Input:` live `CAM_A` stream only
- `Output:` encoded file at `--output` plus a `Video` topic for preview
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/video_saver.py](utils/video_saver.py)
- [utils/arguments.py](utils/arguments.py)
- [backend-run.sh](backend-run.sh)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) captures `CAM_A` as `640x480` NV12 frames.
- `dai.node.VideoEncoder` runs on-device using the selected codec profile.
- [utils/video_saver.py](utils/video_saver.py) receives already-encoded packets and muxes them directly into the requested container file with PyAV.
- The preview path is separate from the saved stream: `Video` shows raw frames for `h265` or any RVC4 run, because encoded visualizer support is limited there.

## Constraints

- The source resolution is fixed to `640x480` in [main.py](main.py).
- There is no replay mode; this is only for live camera capture.
- In standalone mode the output file is written inside the app runtime environment on the device side, not onto the host filesystem automatically.
- The default output name is `video.mp4` regardless of codec, so container/codec expectations should be checked explicitly.

## Related Examples

- [streaming/rtsp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/rtsp-streaming): use this when you need live H265 delivery instead of a saved file
- [streaming/mjpeg-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/mjpeg-streaming): use this when you need browser-viewable streaming instead of recording
- [streaming/poe-tcp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/poe-tcp-streaming): use this when you need a custom network transport rather than local muxing

## Validation

- `Run:` `python3 main.py`
- `Codec override:` `python3 main.py --codec h265 --output video_h265.mp4`
- `Success looks like:` the Visualizer shows `Video`, quitting cleanly leaves an output file on disk, and VLC can open the result
- `Common failure meaning:` the runtime cannot write the output path, the player does not support the chosen codec, or standalone output was assumed to appear on the host automatically
