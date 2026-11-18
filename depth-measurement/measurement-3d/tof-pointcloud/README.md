# ToF Point Cloud

This example aligns [ToF](https://docs.luxonis.com/hardware/platform/depth/tof/) depth to the color camera and streams a colorized point cloud to the DepthAI Visualizer. The ToF range profile (close, mid, or far) can be switched at runtime with keyboard controls in the Visualizer.

The device needs a ToF sensor and a color camera. The color camera is `CAM_A` on RVC4 and `CAM_C` on RVC2.

## Usage

Running this example requires a **Luxonis device** with a ToF sensor connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the ToF and color cameras. (default: 30)
```

The Visualizer shows a `Point Cloud` topic in the 3D view, and a `Color` stream with the `ToF Mode` overlay that shows the active range profile.

### Keyboard Controls

Press the keys while the Visualizer window is focused.

| Key | Description                     |
| --- | ------------------------------- |
| `1` | Close range ToF profile         |
| `2` | Mid range ToF profile           |
| `3` | Far range ToF profile (default) |
| `q` | Quit the example                |

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/).

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

```bash
python3 main.py --device <DEVICE_IP>
```

This will run the example on a specific device.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
