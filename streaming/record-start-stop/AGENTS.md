# AGENTS.md

## Summary

This example records H.264 clips with `dai.node.RecordVideo` and shows a live preview with a record indicator. A key starts and stops a segment, and an optional script node does the same from person or face detections.

## Use This Example When

- You need to start and stop `RecordVideo` segments from the host.
- You need the pre-trigger buffer and the frame, duration, and size limits on one segment.
- You need a device script to send `RecordControl` from `DetectionNetwork` results.

## Do Not Use This Example When

- You need one continuous file with no start or stop control. Use on-device encoding for that.
- You need holistic record or replay of every camera stream.
- You need H.265, MJPEG, or raw `.dai` frames. This example records H.264 video.

## Quick Facts

- `Category:` `streaming/record-start-stop`
- `Shape:` `script+standalone`
- `Primary task:` start and stop H.264 `RecordVideo` segments from a key or from detections
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` `CAM_A`, Model Zoo access, and a depthai build with `RecordControl`
- `Input:` live `CAM_A` only
- `Output:` `recordings/start-stop_<time>/frames.mp4` and `frames.mcap`, plus Visualizer topics `Video`, `Detections`, and `Recording`
- `Models:` YOLOv6 COCO or YuNet YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/trigger_script.py](utils/trigger_script.py)
- [utils/record_bridge.py](utils/record_bridge.py)
- [utils/recording_indicator.py](utils/recording_indicator.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) opens `CAM_A` and runs `dai.node.DetectionNetwork` on the `--target` model, or on `--model` when that is set.
- The detector passthrough is the preview. An `ImageManip` converts it to NV12 and a `VideoEncoder` produces H.264 for `RecordVideo`.
- `RecordVideo` waits for a trigger. `setPreTriggerFrames` defaults to 60. Each start carries `--max-frames`, `--max-duration-ms`, and `--max-size-kb`.
- [utils/recording_indicator.py](utils/recording_indicator.py) reads `record.getStatus()` and publishes a round mark plus `REC`, `IDLE`, or `ERROR` on the preview. The mark is a filled `LINE_LOOP`. `CircleAnnotation` is drawn red and stretched tall on a wide frame. The annotation output is named `output` because `HostNode` already uses `out`.
- With `--auto-record` (the default), [utils/trigger_script.py](utils/trigger_script.py) is loaded into `dai.node.Script`. Detections go into that script. The `r` key goes into the script too, so the script owns the manual hold and the 2 second suppression.
- On RVC4 the script builds `RecordControl` and its `control` output is the only link to `record.inputControl`. `RecordVideo.status` is linked into the script.
- On RVC2 the stock script firmware has no `RecordControl` or `RecordStatus`. The script sends a one-byte `Buffer` (`1` start, `0` stop). [utils/record_bridge.py](utils/record_bridge.py) turns that into `RecordControl` on the host. The host loop forwards later record status as the same kind of `Buffer` (`1` started, `0` stopped, `2` error), so a limit expiry can open the next segment while the label is still visible.
- With `--no-auto-record` the script is not created. The key sends `RecordControl` straight to `record.inputControl`. The detector still draws boxes.

## Data Flow

- `Camera` -> `DetectionNetwork` passthrough -> Visualizer `Video`, `RecordingIndicator`, and `ImageManip`.
- `ImageManip` NV12 -> `VideoEncoder` H.264 -> `RecordVideo.input`.
- `DetectionNetwork.out` -> Visualizer `Detections`, and, when the script exists, `Script.detections`.
- On RVC4, `RecordVideo.status` -> `Script.status`. On RVC2, the host reads `getStatus()` and forwards a `Buffer` to `Script.status` after the node has started once.
- Host key -> `record.inputControl` when the script is off. With the script, the key goes to `Script.manual`, and `Script.control` reaches `record.inputControl` either directly or through `RecordCommandBridge`.

## Constraints

- A limit value of 0 is rejected. `RecordControl` ignores a whole start when any of the three limits is 0. Use -1 to leave a limit off.
- Reaching a limit closes the segment and leaves the node idle. It does not open the next segment by itself. In auto mode the script starts a new segment on the next matching detection.
- The auto script stops a segment after 2 seconds with no matching detection. That duration is `ABSENCE_SECONDS` in [utils/trigger_script.py](utils/trigger_script.py).
- A manual stop suppresses auto start until the label has been absent for those 2 seconds, so a person who is still in frame does not immediately restart the clip.
- A manual start keeps recording through the absence timeout. A limit or the `r` key still ends it.
- RVC4 script firmware provides `RecordControl` and `RecordStatus`. RVC2 script firmware does not, so auto mode on RVC2 must not mention those names. `--no-auto-record` sends control from the host on every platform.
- On RVC2, `RecordVideo` runs on the host. On RVC4 it runs on the device and the files are copied to `--output-dir` when the pipeline stops.
- H.264 segments become decodable at an IDR. The encoder preset uses one keyframe period per second at the selected fps. Frames before that IDR, including part of the pre-trigger buffer, can be dropped from the file.
- RVC2 H.264 needs a width multiple of 32 and a height multiple of 8. The default models satisfy that. A custom model that does not is rejected before the pipeline starts.
- The default labels are `person` for YOLOv6 and `face` for YuNet, matched case-insensitively against `labelName` and the class index. Auto mode exits if the model lists classes and none of the requested labels are present.
- Later segments are `frames_s1.mp4`, `frames_s2.mp4`, and so on, beside `frames.mcap`.

## Related Examples

- [streaming/on-device-encoding](https://github.com/luxonis/oak-examples/tree/main/streaming/on-device-encoding): use this when you need one continuous encoded file and no start or stop control
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you need a single detection model without recording
- [neural-networks/face-detection/blur-faces](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/blur-faces): use this when you need the YuNet face model for something other than a record trigger

## Validation

- `Run:` `python3 main.py`
- `Manual only:` `python3 main.py --no-auto-record`
- `Faces:` `python3 main.py --target face`
- `Limits:` `python3 main.py --max-frames 100 --max-duration-ms 4000 --max-size-kb 512 --pretrigger-frames 60`
- `Success looks like:` the Visualizer shows `Video`, `Detections`, and a `REC` or `IDLE` mark. `r` changes that mark. Auto mode changes it when the selected label appears and about 2 seconds after it disappears. Quitting leaves `frames.mp4` under `recordings/start-stop_<time>/`.
- `Common failure meaning:` the installed depthai has no `RecordControl` API, an RVC2 script still names `RecordControl` and the device reconnects, Model Zoo access failed, or RVC4 did not copy the recording because the pipeline did not stop cleanly.
