# Thermal Person Detection

This example demonstrates person detection with a thermal camera. We trained a custom YOLOv6-Nano based object detection model on a mixed dataset made from our synthetic images, [FLIR](https://www.flir.eu/oem/adas/adas-dataset-form/) dataset and some smaller datasets from [Roboflow](https://universe.roboflow.com/search?q=class%3Athermal+camera). We used [Thermal Person Detection](https://models.luxonis.com/luxonis/thermal-person-detection/b1d7a62f-7020-469c-8fa9-a6d1ff3499b2) model from HubAI to detect people in the thermal image.

> **Note:** Running this example requires a **Luxonis Thermal device** connected to your computer. You can find more information about it [here](https://docs.luxonis.com/hardware/products/OAK%20Thermal).

## Demo

![Exampe](media/thermal_person.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-m MODEL, --model MODEL
                      HubAI model reference. (default: luxonis/thermal-person-detection:256x192)
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 20)
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

This will run the example with the default arguments.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
