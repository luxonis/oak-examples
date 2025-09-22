# Collision Avoidance

This example's goal is to detect the objects moving towards the camera and alert the user if it can be dangerous pass. We use our [YOLOv6 nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model for detecting the desired objects. By default, it detects the class `person` but it can be easily changed to any other class like `car`, `bicycle`, etc. (just modify the variable in the `main.py` file). The app also tracks the objects and estimates their position in 3D space using our depth cameras (you need to have depth-enabled cameras connected). Dangerous pass is detected when the object is moving towards the camera, this is done by checking the direction of the object's trajectory.

You can see the visualization of the object's trajectory in the `Direction` topic. We also visualize the bird's eye view of the scene.

> **Note:** This example requires a device with at least 3 cameras (color, left and right) since it utilizes the `StereoDepth` node.

## Demo

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

This will run the example with the default device.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
