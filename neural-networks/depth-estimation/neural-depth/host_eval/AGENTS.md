# AGENTS.md

## Summary

This is the repository reference for offline NeuralDepth evaluation on stereo datasets. Use it when you need accuracy metrics and saved outputs from host-supplied stereo pairs instead of a live visualizer demo.

## Use This Example When

- You need NeuralDepth accuracy evaluation on a dataset.
- You want EPE, bad-pixel metrics, and density reported per scene and in aggregate.
- You need host-supplied stereo pairs sent to a connected device.

## Do Not Use This Example When

- You need a live camera demo.
- You need standalone packaging.
- You need generic stereo benchmarking unrelated to NeuralDepth.

## Quick Facts

- `Category:` `neural-networks/depth-estimation/neural-depth/host_eval`
- `Shape:` `eval`
- `Primary task:` evaluate NeuralDepth variants on stereo datasets
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only; requires a reachable device and a stereo dataset on disk
- `Requires:` dataset scenes with `im0.png`, `im1.png`, and optional `disp0.pfm`
- `Input:` host-loaded stereo image pairs
- `Output:` saved `disparity.png` files plus printed metrics
- `Models:` NeuralDepth device-zoo variants mapped in [main.py](main.py)
- `Visualizer / UI:` none

## Read First

- [README.md](https://github.com/luxonis/oak-examples/blob/main/neural-networks/depth-estimation/neural-depth/README.md)
- [main.py](main.py)
- [utils/utils.py](utils/utils.py)
- [utils/arguments.py](utils/arguments.py)
- [utils/middlebury_download.py](utils/middlebury_download.py)

## Architecture

- The script walks a dataset folder and finds scenes containing left/right stereo images.
- It maps the requested NeuralDepth variant to a device-zoo model and inference size.
- Host code wraps the stereo images into `dai.ImgFrame` messages and sends them to a `NeuralNetwork` node through explicit input queues.
- Predictions are postprocessed into disparity visualizations and metric summaries and then written to the output directory.

## Constraints

- This is not a Visualizer example; it writes files and prints metrics.
- The CLI uses `--device_ip`, not the usual `--device`.
- Dataset layout is opinionated and effectively Middlebury-style.
- Metric computation is only available when ground-truth disparity exists.

## Related Examples

- [neural-networks/depth-estimation/neural-depth](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/neural-depth): use this when you need the live NeuralDepth demo
- [neural-networks/depth-estimation/foundation-stereo](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/foundation-stereo): use this when you want a heavy host stereo comparison baseline
- [depth-measurement/stereo-on-host](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-on-host): use this when you need host stereo comparison rather than NeuralDepth evaluation

## Validation

- `Run:` `python3 main.py --dataset <DATASET_DIR> --output <OUTPUT_DIR> --device_ip <IP>`
- `Success looks like:` per-scene outputs are written under the output directory and aggregate metrics print at the end
- `Common failure meaning:` the dataset layout is wrong, the target device is unreachable, or the chosen NeuralDepth variant does not match the intended evaluation setup
