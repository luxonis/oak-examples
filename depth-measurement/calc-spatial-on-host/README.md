# Calculate spatial coordinates on the host

This example shows how to calcualte spatial coordinates of a ROI on the host and gets depth frames from the device. Other option is to use [SpatialLocationCalculator](https://docs.luxonis.com/projects/api/en/latest/components/nodes/spatial_location_calculator/) to calcualte spatial coordinates on the device.

If you already have depth frames and ROI (Region-Of-Interest, eg. bounding box of an object) / POI (Point-Of-Interest, eg. feature/key-point) on the host, it might be easier to just calculate the spatial coordiantes of that region/point on the host, instead of sending depth/ROI back
to the device.

> **Note**: Using single points / tiny ROIs (eg. 3x3) should be avoided, as depth frame can be noisy, so you should use **at least 10x10 depth pixels
> ROI**. Also note that to maximize spatial coordinates accuracy, you should define min and max threshold accurately.

## Demo

![Demo](https://user-images.githubusercontent.com/18037362/146296930-9e7071f5-33b9-45f9-af21-cace7ffffc0f.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
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
