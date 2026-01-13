# NeuralDepth Host Evaluation

This pipeline evaluates NeuralDepth models on stereo datasets by sending image pairs from the host to an OAK device and computing disparity accuracy metrics.

**Looking for other NeuralDepth examples?**
- [Check depthai pipelines using NeuralDepth node](https://github.com/luxonis/depthai-core/tree/main/examples/python/NeuralDepth)


## Dataset Setup

Download the Middlebury 2014 stereo dataset using the provided utility:

```bash
cd utils
python middlebury_download.py
```

This creates a `data/` folder with `perfect/` and `imperfect/` subfolders containing scene directories.
All 23 scenes with ground truth disparity are downloaded and used, if you need only 10 train scenes filtering is needed.

The `StereoDataSample` class in `utils/utils.py` is designed for the Middlebury dataset format (left: `im0.png`, right: `im1.png`, ground truth: `disp0.pfm`). Modify it to support other stereo dataset formats.

## Usage


```bash
python main.py --model {NANO,SMALL,MEDIUM,LARGE} --dataset <path> --output <path> --device_ip <ip>
```

## Eval Notes

> Images are resized with preserved aspect ratio and padded to evaluation size 800x1280.

## Output

For each scene, the pipeline generates:
- `disparity.png`: Colorized disparity map with metrics overlay
- Console output: Per-scene and average metrics (EPE, Bad1-4, Density)

## Comments on choices of post-processing:
In practice not all usecase require full density (predictions for 100% of pixels) and a small tradeoff can be acceptable to filter out less reliable pixels and/or occlusions.<br>
For example 3D usecases that rely on clean pointclouds can benefit a lot from reliable and robust filtering that can offer an accuracy boost and suppression of unreliable pixels, unconfident regions and border regions to offer cleaner pointclouds.<br>

The above is the main reason `confidence` and `edge` predictions are provided, and why border-erasure postprocessing is used (border pixel are less likely to have matching points between images and can introduce noise to pointclouds).

Most importantly all these post-processing choices are __optional__, full disparity map is available with `confidence` and `edge` maps for the user to choose how to use them or not.
