# General OCR

We provide here an example for running a two stage text detection and OCR pipeline. This example uses PaddlePaddle [Text Detection](https://models.luxonis.com/luxonis/paddle-text-detection/131d855c-60b1-4634-a14d-1269bb35dcd2) and [Text Recognition](https://models.luxonis.com/luxonis/paddle-text-recognition/9ae12b58-3551-49b1-af22-721ba4bcf269) models from HubAI Model ZOO. The example visualizes the recognized text on an adjacent white image in the locations in which it was detected. This example showcases how a two stage pipeline can easily be built using DepthAI.

## Demo

![Detection Output](media/highway-sign-ocr.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: the first locally available device is used)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 5 for both RVC2 and RVC4)
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

This will run the example with the default device and camera input.

```bash
python3 main.py --media <PATH_TO_VIDEO>
```

This will run the example with the default device and the video file.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
