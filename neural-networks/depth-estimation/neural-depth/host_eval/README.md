# NeuralDepth Host Evaluation

This pipeline evaluates NeuralDepth models on stereo datasets by sending image pairs from the host to an OAK device and computing disparity accuracy metrics.

> **Note:** RVC4 peripheral mode only.

**Eval Notes:**
Images are resized with preserved aspect ratio and padded to evaluation size 800x1280.

## Prerequisites

First you have to make sure evaluation dataset is downloaded. In this example we use the [Middlebury 2024 stereo dataset](https://vision.middlebury.edu/stereo/data/scenes2014/) and you can download it by running:

```bash
cd utils
python middlebury_download.py --calibration {perfect,imperfect} --max_scenes <N> --output <path>
```

This creates a `data/` folder with `perfect/` and `imperfect/` subfolders containing scene directories.

The `StereoDataSample` class in `utils/utils.py` is designed for the Middlebury dataset format (left: `im0.png`, right: `im1.png`, ground truth: `disp0.pfm`). Modify it to support other stereo dataset formats.

## Usage

Running this example requires a **RVC4 Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example using your computer as host in ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```bash
  -m {NANO,SMALL,MEDIUM,LARGE}, --model {NANO,SMALL,MEDIUM,LARGE}
                        Model variant to use. One of `['NANO', 'SMALL', 'MEDIUM', 'LARGE']`. (default: LARGE)
  --dataset DATASET     Path to the dataset folder. (default: data/imperfect)
  -o OUTPUT, --output OUTPUT
                        Output folder for evaluation results. (default: outputs_neural_depth_eval)
  -d DEVICE_IP, --device_ip DEVICE_IP
                        IP address of the device to connect to. (default: None)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python main.py
```

This will run the example with default arguments.

```bash
python main.py -m NANO
```

This will run the example with `NANO` model variant.

### Output

For each scene, the pipeline generates:

- `disparity.png`: Colorized disparity map with metrics overlay
- Console output: Per-scene and average metrics (EPE, Bad1-4, Density)

### Metrics

| -                                                                         | EPE   | Bad2  | Bad4 |
| ------------------------------------------------------------------------- | ----- | ----- | ---- |
| Middlebury 2014 (train 10 scenes) / perfect / SNPE v2.32.0                | 1.55  | 12.45 | 5.56 |
| Middlebury 2014 (train 10 scenes) / imperfect / SNPE v2.32.0              | 1.62  | 13.22 | 5.42 |
| Middlebury 2014 (train + additional 23 scenes) / perfect / SNPE v2.32.0   | 1.374 | 10.36 | 4.29 |
| Middlebury 2014 (train + additional 23 scenes) / imperfect / SNPE v2.32.0 | 1.44  | 11.03 | 4.48 |
| Middlebury 2014 (train + additional 23 scenes) / perfect / SNPE v2.33.6   | 1.15  | 8.09  | 2.9  |

## Comments on choices of post-processing:

In practice not all usecase require full density (predictions for 100% of pixels) and a small tradeoff can be acceptable to filter out less reliable pixels and/or occlusions.<br>
For example 3D usecases that rely on clean pointclouds can benefit a lot from reliable and robust filtering that can offer an accuracy boost and suppression of unreliable pixels, unconfident regions and border regions to offer cleaner pointclouds.<br>

The above is the main reason `confidence` and `edge` predictions are provided, and why border-erasure postprocessing is used (border pixel are less likely to have matching points between images and can introduce noise to pointclouds).

Most importantly all these post-processing choices are __optional__, full disparity map is available with `confidence` and `edge` maps for the user to choose how to use them or not.
