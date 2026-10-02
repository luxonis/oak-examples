# AGENTS.md

## Summary

This is the repository reference for comparing three host-side ways to view encoded OAK video. Use it when you need to reason about encoded-stream playback rather than capture or network delivery.

## Use This Example When

- You need to compare direct Visualizer playback with host-side decode.
- You want to test `h264`, `h265`, and `mjpeg` playback behavior.
- You need camera or replay input while keeping the stream encoded on the device side.

## Do Not Use This Example When

- You need a network streaming protocol like RTSP or MJPEG-over-HTTP.
- You need on-device recording to a file rather than host playback.
- You need a single script that preserves `h265` in the Visualizer path.

## Quick Facts

- `Category:` `tutorials/play-encoded-stream`
- `Shape:` `multi-entrypoint+standalone-service`
- `Primary task:` play encoded camera or replay streams through different host decode paths
- `Entrypoints:` [main.py](main.py), [pyav.py](pyav.py), and [opencv.py](opencv.py)
- `Standalone path:` [oakapp.toml](oakapp.toml), running [main.py](main.py)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` camera or replay media, and for the alternate paths, PyAV or OpenCV decode support
- `Input:` live camera by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` topic in the Visualizer
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [pyav.py](pyav.py)
- [opencv.py](opencv.py)
- [utils/decode_video_av.py](utils/decode_video_av.py)
- [utils/decode_video_cv2.py](utils/decode_video_cv2.py)
- [utils/encoder_profiles.py](utils/encoder_profiles.py)

## Architecture

- [main.py](main.py) sends the encoded bitstream directly to the Visualizer.
- [pyav.py](pyav.py) decodes the encoded packets with PyAV and republishes decoded frames.
- [opencv.py](opencv.py) uses OpenCV `imdecode` for MJPEG-only playback.
- All three scripts share the same camera-or-replay input pattern and the same encoder profile table.

## Constraints

- [main.py](main.py) silently downgrades requested `h265` playback to `h264`, because the Visualizer path does not support `h265` there.
- [opencv.py](opencv.py) forces `mjpeg` even if the user requested another codec.
- [oakapp.toml](oakapp.toml) packages only [main.py](main.py), not the decode-alternative scripts.

## Related Examples

- [streaming/on-device-encoding](https://github.com/luxonis/oak-examples/tree/main/streaming/on-device-encoding): use this when you need encoded recording instead of playback comparison
- [streaming/rtsp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/rtsp-streaming): use this when you need a standard streaming endpoint instead of local playback
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when you need the simplest encoded preview path without comparing decoders

## Validation

- `Visualizer path:` `python3 main.py`
- `PyAV path:` `python3 pyav.py`
- `Success looks like:` the selected script shows a `Video` topic and the behavior matches its codec limitations
- `Common failure meaning:` the wrong decoder path was chosen for the requested codec, or the user assumed all codecs behave identically in the Visualizer route
