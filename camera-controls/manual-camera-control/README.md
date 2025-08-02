# Manual Camera Control

This example demonstrates how to manually control different camera parameters. Use keyboard to modify different settings.

## Demo

![example](media/example.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 30)
```

### Keyboard Controls

| Key      | Description                          |
| -------- | ------------------------------------ |
| `c`      | Capture an image                     |
| `e`      | Autoexposure                         |
| `t`      | Trigger autofocus                    |
| `f`      | Autofocus (continuous)               |
| `w`      | Auto white balance lock (true/false) |
| `r`      | Auto exposure lock (true/false)      |
| `+`, `-` | Increase/decrease selected control   |

The following controls can be selected and modified with `+` and `-` keys:

| Key | Description                |
| --- | -------------------------- |
| `1` | Manual exposure time       |
| `2` | Manual sensitivity ISO     |
| `3` | Auto white balance mode    |
| `4` | Auto exposure compensation |
| `5` | Anti-banding/flicker mode  |
| `6` | Effect mode                |
| `7` | Brightness                 |
| `8` | Contrast                   |
| `9` | Saturation                 |
| `0` | Sharpness                  |
| `o` | Manual white balance       |
| `p` | Manual focus               |
| `[` | Luma denoise               |
| `]` | Chroma denoise             |

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

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
