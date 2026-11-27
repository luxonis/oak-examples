# AGENTS.md

## Summary

This is the repository reference for encoding video on the OAK device and writing that bitstream to a file without host-side decode or re-encode. `h264` and `mjpeg` `.mp4` files use `dai.node.RecordVideo`. `h265` and any other container use PyAV.

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
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` `CAM_A`, filesystem access to the output path, and PyAV when the codec is `h265` or the output extension is not `.mp4`
- `Input:` live `CAM_A` stream only
- `Output:` encoded file at `--output`, finalized when the pipeline stops, plus a `Video` topic for preview
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/video_saver.py](utils/video_saver.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) captures `CAM_A` as `640x480` NV12 frames.
- `dai.node.VideoEncoder` runs on-device using the selected codec profile.
- For `h264` or `mjpeg` with an output path whose suffix is `.mp4`, `video_enc.out` is linked to `dai.node.RecordVideo.input`. The node gets `setRecordVideoFile(--output)` and `setFps(--fps_limit)`. No metadata file is set.
- Otherwise [utils/video_saver.py](utils/video_saver.py) muxes the encoded packets with PyAV. `run` closes the container in a `finally` block after the input closes, which writes the trailer.
- The preview path is separate from the saved stream: `Video` shows raw frames for `h265` or any RVC4 run, because encoded visualizer support is limited there.

## Constraints

- The source resolution is fixed to `640x480` in [main.py](main.py).
- There is no replay mode, so `RecordVideo` is not given a metadata path and no `.mcap` is written.
- `RecordVideo` rejects H.265 in `VIDEO` format and rejects an encoded path whose extension is not `.mp4`. The extension check is case-sensitive.
- `RecordVideo` writes each sample at `1 / --fps_limit`. It does not store the device timestamp. The PyAV path stamps each packet in microseconds from the first frame. A container may rescale that (Matroska stores 1/1000). The packet time base stays 1 µs because reading it back from the stream after the first packet is wrong for Matroska.
- `RecordVideo.input` keeps its default queue: non-blocking, 15 messages, oldest dropped when full. The PyAV input matches the old Sync input: non-blocking, 10 messages.
- On the current DepthAI build, an RVC4 `RecordVideo` fed by encoded frames runs on the device. The file is copied to `--output` when the pipeline stops. On RVC2, and on `depthai==3.11.0`, the same node runs on the host and writes that path during the run. `setRunOnHost` is left unset.
- In standalone mode the output path is inside the app runtime, not the computer that ran `oakctl`. The RVC4 copy still happens at pipeline stop.
- The default output name is `video.mp4` and the default codec is `h264`, so the default command uses `RecordVideo`.

## Related Examples

- [streaming/rtsp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/rtsp-streaming): use this when you need live H265 delivery instead of a saved file
- [streaming/mjpeg-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/mjpeg-streaming): use this when you need browser-viewable streaming instead of recording
- [streaming/poe-tcp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/poe-tcp-streaming): use this when you need a custom network transport rather than local muxing

## Validation

- `Run:` `python3 main.py` saves H.264 to `video.mp4` with `RecordVideo`
- `MJPEG:` `python3 main.py --codec mjpeg --output video_mjpeg.mp4`
- `PyAV paths:` `python3 main.py --codec h265 --output video_h265.mp4` and `python3 main.py --codec h264 --output video.mkv`
- `Success looks like:` the Visualizer shows `Video`. Quitting stops the pipeline and leaves a complete file at `--output`. VLC can open it. `ffprobe` reports `h264` or `mjpeg` for the `RecordVideo` files and `hevc` for the H.265 file. The `RecordVideo` file is present after the pipeline stops, not necessarily while it is still running on RVC4.
- `Common failure meaning:` the runtime cannot write the output path, the player does not support the chosen codec, the RVC4 firmware has no `RecordVideo` node, or standalone output was assumed to appear on the computer that ran `oakctl`
