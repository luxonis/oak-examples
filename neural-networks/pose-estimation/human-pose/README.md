# Human Pose Estimation

This example demonstrates how to build a 2-stage DepthAI pipeline for human pose estimation. The pipeline consists of [YOLOv6 nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) object detector and [Lite-HRNet](https://models.luxonis.com/luxonis/lite-hrnet/c7c9e353-9f6d-43e1-9b45-8edeae82db70) pose estimation model. The example works on both RVC2 and RVC4. For realtime application you will need to use OAK4 cameras.

As an alternative you can use the end-to-end [YOLOv8 Nano Pose Estimation](https://models.luxonis.com/luxonis/yolov8-nano-pose-estimation/12acd8d7-25c0-4a07-9dff-ab8c5fcae7b1) or [YOLOv8 Large Pose Estimation](https://models.luxonis.com/luxonis/yolov8-large-pose-estimation/8be178a0-e643-4f1e-b925-06512e4e15c7) models with [generic example](../../../generic-example/).

There are 4 models available for the [Lite-HRNet models](https://models.luxonis.com/luxonis/lite-hrnet/c7c9e353-9f6d-43e1-9b45-8edeae82db70). If you choose to use a different model please adjust `fps_limit` accordingly.

## Demo

[![Human pose estimation](media/dance.gif)](media/dance.gif)

<sup>[Source](https://www.youtube.com/watch?v=91sd4Jnwgjs)</sup>

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-m MODEL, --model MODEL
                    Pose model to run the inference on. (default: luxonis/lite-hrnet:18-coco-192x256)
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 5 for RVC2 and 30 for RVC4)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
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
python3 main.py
```

This will run the human pose estimation example with the default device, default model, and camera input.

```bash
python3 main.py --media <PATH_TO_VIDEO>
```

This will run the human pose estimation example with the default device and the video file.

```bash
python3 main.py --model luxonis/lite-hrnet:30-coco-192x256 --fps_limit 5
```

This will run the human pose estimation example with the default device and camera input, but with the `luxonis/lite-hrnet:30-coco-192x256` model and a `5` FPS limit.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
