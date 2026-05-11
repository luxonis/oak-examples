# AGENTS.md

## Summary

This is the repository reference for running simple custom converted models packaged as local `NNArchive` files. Use it when you need the repo’s clearest example of loading your own converted model artifacts instead of fetching a model-zoo slug.

## Use This Example When

- You need a tutorial for loading local custom model archives.
- You want lightweight image-processing models rather than detectors.
- You need both a combined demo and smaller per-model entrypoints.

## Do Not Use This Example When

- You need a standard zoo model or a detection tutorial.
- You need the model-conversion scripts alone without the runtime examples.
- You need a standalone package that lets you choose among all entrypoints at runtime.

## Quick Facts

- `Category:` `tutorials/custom-models`
- `Shape:` `multi-entrypoint+standalone`
- `Primary task:` run local custom `NNArchive` models for blur, edge, concat, and frame-diff operations
- `Entrypoints:` [main.py](main.py), [blur.py](blur.py), [edge.py](edge.py), [concat.py](concat.py), and [diff.py](diff.py)
- `Standalone path:` [oakapp.toml](oakapp.toml) packages [main.py](main.py)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` local archives in [models/](models/) and, for concat or the combined demo, `CAM_A`, `CAM_B`, and `CAM_C`
- `Input:` live camera streams only
- `Output:` Visualizer topics such as `Blur`, `Edge`, `Concat`, `Diff`, and `Passthrough`
- `Models:` local archives in [models/](models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [blur.py](blur.py)
- [edge.py](edge.py)
- [concat.py](concat.py)
- [diff.py](diff.py)
- [utils/colorize_diff.py](utils/colorize_diff.py)
- [generate_model/README.md](generate_model/README.md)

## Architecture

- The runtime examples load local `.tar.xz` archives from [models/](models/) rather than using model-zoo YAML descriptors.
- [main.py](main.py) runs all four custom models at once: blur, edge, three-input concat, and previous-frame diff.
- [diff.py](diff.py) and the diff branch in [main.py](main.py) use a `Script` node to pair the previous and current frame.
- [concat.py](concat.py) and [main.py](main.py) use three cameras and wire them into named inputs `img1`, `img2`, and `img3`.
- [generate_model/](generate_model/) contains the PyTorch/Kornia source used to create these archives, but packaging/runtime flows do not regenerate them automatically.

## Constraints

- [oakapp.toml](oakapp.toml) always runs [main.py](main.py); it does not expose the smaller per-model scripts.
- The combined demo in [main.py](main.py) requires three cameras because it includes the concat model path.
- This folder is about loading already-converted model archives; it is not a generic conversion pipeline by itself.

## Related Examples

- [../../neural-networks/generic-example](../../neural-networks/generic-example/): use this when you need the generic model-zoo single-model scaffold
- [../camera-demo](../camera-demo/): use this when you need a minimal camera baseline without custom models
- [../display-detections](../display-detections/): use this when the tutorial should stay in the detector/annotation space instead of image-processing models

## Validation

- `Run all:` `python3 main.py`
- `Run one model:` `python3 blur.py`
- `Success looks like:` the Visualizer shows the expected output topics and the chosen custom model changes the image in the way implied by its name
- `Common failure meaning:` the local model archives are missing, the wrong camera count is available for concat, or the user expects `oakapp.toml` to package every alternate script
