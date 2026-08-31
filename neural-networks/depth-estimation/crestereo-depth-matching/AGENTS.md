# AGENTS.md

## Summary

This is the repository reference for comparing CREStereo neural stereo matching against unified DepthAI depth. Use it when you need a neural stereo model and a `dai.node.Depth` baseline in the same visualizer session.

## Use This Example When

- You need a neural stereo depth reference.
- You want to compare CREStereo-derived depth against DepthAI `Depth` output.
- You need the supported CREStereo model variants and platform restrictions documented in one place.

## Do Not Use This Example When

- You need host-side stereo benchmarking with external models.
- You need RGBD point clouds or spatial detections.
- You need depth from a monocular model.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/crestereo-depth-matching`
- `Shape:` `script+standalone`
- `Primary task:` compare CREStereo-derived depth with `Depth`
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` stereo-capable RVC2 and RVC4 devices with platform-specific supported model variants
- `Requires:` `CAM_B/C` stereo pair and supported CREStereo model slug for the platform
- `Input:` stereo camera pair only
- `Output:` `Depth` and `CREStereo Depth`
- `Models:` default CREStereo YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- Stereo mono cameras on `CAM_B` and `CAM_C` feed the CREStereo neural model path; `Depth` owns its own depth-source wiring.
- `Sync` and `MessageDemux` provide left/right inputs for the CREStereo network.
- The neural path uses `ParsingNeuralNetwork`; RVC4 explicitly sets the `snpe` DSP backend.
- [utils/disparity_to_depth.py](utils/disparity_to_depth.py) converts CREStereo disparity to depth using calibration before visualization.
- `ApplyDepthColormap` visualizes both metric-depth outputs side by side.

## Constraints

- Supported model slugs are hardcoded by platform in [main.py](main.py).
- There is no media replay path; this example is stereo-camera only.
- Default FPS is intentionally low, especially on RVC2.

## Related Examples

- [neural-networks/depth-estimation/foundation-stereo](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/foundation-stereo): use this when you need a heavier host-run stereo model baseline
- [neural-networks/depth-estimation/neural-depth](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/neural-depth): use this when you need Luxonis NeuralDepth on RVC4
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you want host-side stereo comparison rather than on-device neural disparity

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows `Depth` and `CREStereo Depth`, and both streams update from the stereo pair
- `Common failure meaning:` the chosen model is unsupported for the platform, the device lacks stereo cameras, or the requested FPS/model size is too heavy for the hardware
