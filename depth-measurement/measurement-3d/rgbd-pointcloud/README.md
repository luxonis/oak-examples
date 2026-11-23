# RGB-D projection Demo

This example shows how to align depth to rgb camera frame and project depth map into 3D pointcloud. You can also choose to skip rgb-depth alignment and colorize the pointcloud with right mono frame.

**NOTE**: This example requires a device with color camera and stereo cameras.

## Demo

![ezgif-72a39b6d489bd8](https://github.com/user-attachments/assets/2a742929-f080-4a1f-8db5-da356b695876)
![ezgif-7736189d82e875](https://github.com/user-attachments/assets/2cb05ac6-1dca-421b-88a9-d86c05c6e4e1)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
    -d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
    -m, --mono            use mono frame for pointcloud coloring instead of color frame
```

## Holistic replay

Replay is optional. The live path is unchanged. Record and replay with the same `--mono` choice. RGB mode opens `CAM_A` plus the stereo cameras `Depth` opens (`CAM_B` and `CAM_C` on an OAK-D). `--mono` colors the cloud from `CAM_C` and still needs that stereo pair. An RGB recording can be replayed with `--mono`, because the extra `CAM_A` stream is ignored. A `--mono` recording has no `CAM_A` and will not replay as RGB. A failed setup warns `Replay disabled` or `Could not set up holistic replay`. `Replay enabled` is an info line and stays hidden at the default log level.

```bash
mkdir -p recordings
DEPTHAI_RECORD="$PWD/recordings" python3 main.py
DEPTHAI_REPLAY="$PWD/recordings/recording_<time>.tar.gz" python3 main.py
```

Stop the recording with `q`. Do not set `DEPTHAI_RECORD` and `DEPTHAI_REPLAY` together. A device that can run this pipeline is still required. `camera_info.json` replaces the device calibration for that run. On RVC2 the recording is replayed on the host. On RVC4 each camera is replayed on the device. `oakctl app run` does not see these host environment variables.

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

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
