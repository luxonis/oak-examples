# Kalman Filter

This example performs filtering of 2D bounding boxes and spatial coordinates of tracked objects using the Kalman filter.

The Kalman filter is used to obtain better estimates of objects' locations by combining measurements and past estimations. Even when measurements are noisy this filter performs quite well.

Here is a short explanation of the Kalman filter: https://www.youtube.com/watch?v=s_9InuQAx-g.

It uses our [YOLOv6 nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model for detection.

> **Note:** This example requires a device with at least 3 cameras (color, left and right) since it utilizes the `StereoDepth` node.

## Demo

![video](https://user-images.githubusercontent.com/69462196/197813200-236e950e-3dda-403f-b5cd-8d11f0e86124.gif)

In the demo red represents filtered data and blue unfiltered.

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 20 for RVC2 and 30 for RVC4)
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

This will run the Kalman filter example with the default device and camera input.

```bash
python3 main.py --fps_limit 10
```

This will run the Kalman filter example with the default device and 10 FPS limit.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
