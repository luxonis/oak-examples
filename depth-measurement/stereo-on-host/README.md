# Gen3 Stereo on host

> Your device needs to have calibration stored to work with this example

This example demonstrates how [stereo pipeline works](https://docs.luxonis.com/projects/api/en/latest/components/nodes/stereo_depth/#internal-block-diagram-of-stereodepth-node) on the OAK device (using depthai). It rectifies mono frames (receives from the OAK camera) and then uses `cv2.StereoSGBM` to calculate the disparity on the host. It also colorizes the disparity and shows it to the user.

[SSIM score](https://en.wikipedia.org/wiki/Structural_similarity) is used to comapre the similarity between the disparity map calculated using `cv2.StereoSGBM` and the disparity map generated on the OAK camera.

> You can play around with the settings for both methods and use the SSIM score to compare them.

## Demo

<img width="1193" alt="Screenshot 2025-04-24 at 11 43 55" src="https://github.com/user-attachments/assets/4eba827b-7515-432d-b89e-c0c993922313" />

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
