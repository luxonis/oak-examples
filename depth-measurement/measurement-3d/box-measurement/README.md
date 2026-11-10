# Box measurement

This example showcases one possible approach for measuring the size of a box using DepthAI.

![demo](https://github.com/luxonis/oak-examples/blob/master/gen2-multiple-devices/box-measurement/img/demo.gif)

> **⚠️ Known issue:** Due to current CuboidFitter algorithm limitations, measurements may occasionally jump or skip between frames. Active stereo is crucial for stable results, and you may see some instability, especially on RVC2 devices. In some cases, instability can also be caused by insufficient power supply to the device.

The processing node uses depthai-nodes `remap_message` to resample the instance mask and remap detections to the same undistorted RGB stream used by RGBD and the preview, including rotated crops. A host Sync groups the cloud, RGB, and detections within 1 ms. Mask indexing requires an organized cloud of matching dimensions; cuboid projection uses the current RGB transformation intrinsics.

DepthAI 3.11 Align does not preserve arbitrary mask rotations. The shared host remapper is the fallback for same-camera crops, resize, letterbox, and rotation; keep both source and target undistorted.

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 10)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

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
