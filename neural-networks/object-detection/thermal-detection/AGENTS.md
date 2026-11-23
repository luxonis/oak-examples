# AGENTS.md

## Summary

This is the repository reference for person detection on thermal imagery. Use it when you need the thermal-camera-specific object-detection path rather than the normal RGB camera pipeline.

## Use This Example When

- You need thermal person detection.
- You want the repo’s special-sensor detection reference.
- You need to handle thermal-camera YUV422i output before inference.

## Do Not Use This Example When

- You need a normal RGB object detector.
- You need standalone packaging on RVC4.
- You need stereo spatial coordinates.

## Quick Facts

- `Category:` `neural-networks/object-detection/thermal-detection`
- `Shape:` `script`
- `Primary task:` person detection on thermal-camera imagery
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` effectively RVC2/OAK Thermal host mode; replay input is also supported
- `Requires:` Luxonis Thermal hardware for live mode, or compatible replay media
- `Input:` live `dai.node.Thermal` output or replay video
- `Output:` `Video` and `Visualizations`
- `Models:` [depthai_models/thermal_person_detection.RVC2.yaml](depthai_models/thermal_person_detection.RVC2.yaml) when present, or a compatible CLI model slug
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/yuv2bgr.py](utils/yuv2bgr.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- Live mode uses `dai.node.Thermal`. `color` is YUV422i, 256x192. `temperature` is FP16 degrees Celsius and is not linked.
- [utils/yuv2bgr.py](utils/yuv2bgr.py) converts `color` with OpenCV's YUYV decoder into the detector frame type and size. It copies timestamps, sequence number, instance, category, `sourceFb`, `cam`, `event`, and the image transformation. If the model size is not 256x192, the frame is stretched and that scale is stored with `addScale`.
- `ImageManip` is not used on the live path. Its host implementation rejects YUV422i, and the RVC2 preprocessor color-converts NV12 and YUV420p only.
- Replay mode uses `ReplayVideo` plus `ImageManip` to resize and convert NV12 into the detector input shape.
- `ParsingNeuralNetwork` runs the thermal person detector and publishes passthrough plus parsed detections.

## Constraints

- The category overview marks this as a thermal/RVC2-only example in practice.
- There is no `oakapp.toml`; this is not the standalone packaging reference.
- Live mode assumes thermal hardware. `Thermal.color` is YUV422i. Do not replace it with `ImageManip` until that type is supported.
- Do not feed `Thermal.temperature` into this detector. That stream is calibrated temperature, and this model expects the colorized image.
- The host conversion still downloads the thermal frame and uploads BGR to the network. It does not remove that transfer.

## Related Examples

- [neural-networks/object-detection/spatial-detections](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/spatial-detections): use this when you need the normal RGB spatial-detection baseline
- [neural-networks/object-detection/yolo-host-decoding](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-detection/yolo-host-decoding): use this when you need host decoding on standard RGB detections
- [neural-networks/generic-example](https://github.com/luxonis/oak-examples/tree/main/neural-networks/generic-example): use this when you need the generic single-model scaffold on non-thermal input

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Video` and `Visualizations`, and people in thermal imagery are detected
- `Common failure meaning:` the device is not a thermal OAK, the thermal conversion path is broken, or the chosen model does not match the input modality
