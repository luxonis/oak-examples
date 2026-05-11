# AGENTS.md

## Summary

This is the repository reference for host-run Foundation Stereo inference compared against device stereo output. Use it when you need a heavyweight host compute baseline rather than an on-device packaged app.

## Use This Example When

- You need Foundation Stereo specifically.
- You want a host-processing comparison against `StereoDepth`.
- You need control over input resolution profiles and on-demand inference.

## Do Not Use This Example When

- You need standalone packaging.
- You need a lightweight stereo example.
- You need continuous on-device NN inference.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/foundation-stereo`
- `Shape:` `script`
- `Primary task:` compare host-run Foundation Stereo with device disparity
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only; requires a device with color, left, and right cameras
- `Requires:` strong host compute, stereo mono pair, and device IR projector support for the intended baseline
- `Input:` live stereo mono cameras only
- `Output:` `FS Result`, `Disparity`, `Rectified right`, and `Rectified left`
- `Models:` Foundation Stereo is downloaded/managed through [utils/fs_inferer.py](utils/fs_inferer.py) rather than packaged YAML files in this example directory
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/fs_inferer.py](utils/fs_inferer.py)
- [utils/utility.py](utils/utility.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `StereoDepth` produces the device disparity and rectified left/right streams.
- [utils/fs_inferer.py](utils/fs_inferer.py) is a host node that consumes rectified stereo frames and emits Foundation Stereo results.
- Resolution handling comes from [utils/utility.py](utils/utility.py) and the `--resolution` profile.
- The main loop triggers host inference with the `f` key rather than re-running the model every frame automatically.

## Constraints

- This example is intentionally host-only and compute-heavy.
- It expects a device with three cameras and explicitly enables the IR dot projector.
- The model is not packaged through `oakapp.toml`; this is not the right baseline for standalone deployment.

## Related Examples

- [../crestereo-stereo-matching](../crestereo-stereo-matching/): use this when you want an on-device neural stereo baseline
- [../neural-depth](../neural-depth/): use this when you want Luxonis NeuralDepth on RVC4
- [../../../depth-measurement/stereo-on-host](../../../depth-measurement/stereo-on-host/): use this when the main goal is host stereo benchmarking without Foundation Stereo

## Validation

- `Run:` `python3 main.py`
- `Interaction:` press `f` to trigger Foundation Stereo inference
- `Success looks like:` the Visualizer shows rectified frames, device disparity, and `FS Result`
- `Common failure meaning:` host compute is insufficient, the device lacks the required camera topology, or the operator expected continuous inference instead of the current on-demand flow
