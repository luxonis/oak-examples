# Gaze Estimation

This example demonstrates how to run a 3 stage pipeline and multi input models. A gaze estimation example is built to showcase the 3 stage pipeline. The pipeline is composed of the following three models:

- [YuNet](https://models.luxonis.com/luxonis/yunet/5d635f3c-45c0-41d2-8800-7ca3681b1915) is used to detect the faces and their keypoints. Based on this models outputs, the entire face and the eyes are cropped from the original frame.
- The cropped face is used as input to the [Head pose model](https://models.luxonis.com/luxonis/head-pose-estimation/068ac18a-de71-4a6e-9f0f-42776c0ef980) which returns the 3D vector the heads position.
- The cropped eyes and the 3D pose vector are fed into [ADAS gaze estimation model](https://models.luxonis.com/luxonis/gaze-estimation-adas/b174ff1b-740b-4016-b8d5-b9488dbdd657) to compute the final gaze of the person.

## Demo

[![Gaze Example Demo](https://github.com/luxonis/oak-examples/assets/18037362/6c7688e5-30bc-4bed-8455-8b8e9899c5b0)](https://tinyurl.com/5h3dycc5)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 8 for RVC2 and 30 for RVC4)
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

This will run the example with default arguments.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
