# AGENTS.md

## Summary

This example runs native Luxonis `NeuralDepth` or Model Zoo Lite Any Stereo V2 on RVC4 hardware, with matching depth and disparity frame formats. Use it for live neural stereo and native NeuralDepth runtime controls.

## Use This Example When

- You need `dai.node.NeuralDepth` or LAS2 with a common output interface.
- You want to inspect disparity, confidence, and edge outputs together.
- You need keyboard-driven runtime control over the node configuration.

## Do Not Use This Example When

- You need RVC2 compatibility.
- You need host-side stereo model comparison.
- You need dataset evaluation rather than live camera output.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/neural-depth`
- `Shape:` `script+standalone`
- `Primary task:` run Luxonis NeuralDepth live on device
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 only
- `Requires:` stereo mono pair on `CAM_B/C`
- `Input:` full-resolution stereo camera pair
- `Output:` `Depth`, `Disparity`, `Depth Raw`, `Disparity Raw`; native-only `Confidence`, `Edge`, `Controls`
- `Models:` `--backend native|las2`, with backend-specific `--model`; native defaults to `LARGE`, LAS2 to `l-fp16-1280x800`
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/manual_camera_control.py](utils/manual_camera_control.py)
- [utils/arguments.py](utils/arguments.py)
- [utils/las2.py](utils/las2.py)
- [test_outputs.py](test_outputs.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- Native mode feeds full-resolution grayscale stereo outputs into `dai.node.NeuralDepth`.
- LAS2 uses Sync → MessageDemux → Rectification → ParsingNeuralNetwork, followed by a host adapter synchronized with the NN left passthrough. The archive determines the rectified resolution.
- Both expose RAW16 disparity scaled by 16 and RAW16 depth in millimeters, referenced to the rectified left camera. LAS2 derives focal length from frame transformation metadata and uses calibrated translation (centimeters converted to millimeters), matching native geometry. Do not normalize the raw disparity map or derive focal length from unrectified intrinsics.
- Invalid LAS2 disparity maps to zero; conversion saturates uint16 overflow. Preserve frame geometry, timestamps and sequence numbers when adapting output.
- [utils/manual_camera_control.py](utils/manual_camera_control.py) owns the runtime config input queue and keyboard control overlay.
- `ApplyDepthColormap` visualizes depth and disparity; native-only `ApplyColormap` visualizes confidence and edge. LAS2 has no confidence/edge outputs or native runtime controls.

## Constraints

- [main.py](main.py) explicitly raises on non-RVC4 platforms.
- This example is live-camera only; there is no replay input path.
- Native runtime behavior depends on [utils/manual_camera_control.py](utils/manual_camera_control.py).
- Native model choices are derived from `DeviceModelZoo.__members__`; retain legacy aliases. LAS2 choices are the published variants in [utils/arguments.py](utils/arguments.py).
- LAS2 model downloads require internet on first use. Output processing runs on the host in peripheral mode and locally in the OAK App in standalone mode.

## Related Examples

- [neural-networks/depth-estimation/crestereo-depth-matching](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/crestereo-depth-matching): use this when you want another on-device neural stereo baseline
- [host_eval](host_eval/): use this when you need offline dataset evaluation for NeuralDepth
- [depth-measurement/stereo-runtime-configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): use this when you want runtime stereo controls for classic `StereoDepth`

## Validation

- `Run:` `python3 main.py -d <IP>` and `python3 main.py --backend las2 -d <IP>`
- `Success looks like:` both backends show depth/disparity and raw frames; native additionally shows confidence, edge, and responsive controls
- `Common failure meaning:` the device is not RVC4, stereo cameras are unavailable, or the chosen NeuralDepth model is incompatible with the hardware
