# Box measurement

This example showcases one possible approach for measuring the size of a box using DepthAI.

![demo](https://github.com/luxonis/oak-examples/blob/master/gen2-multiple-devices/box-measurement/img/demo.gif)

> **⚠️ Known issue:** Due to current CuboidFitter algorithm limitations, measurements may occasionally jump or skip between frames. Active stereo is crucial for stable results, and you may see some instability, especially on RVC2 devices. In some cases, instability can also be caused by insufficient power supply to the device.

When a box is detected but cannot be measured, its label shows **measurement unavailable** and a reason, such as insufficient valid depth or how many of the three perpendicular faces could be fitted. The confidence score describes detection confidence. Dimensions appear only when the current frame produces a valid cuboid fit.

The video preview uses the same undistorted RGB frame as inference and waits until its measurement overlays are ready, keeping the image and annotations together.

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

## Holistic replay

Replay is optional. The live path is unchanged, and this example has no media flag. A single `ReplayVideo` file would drop the stereo pair, the color camera, and the calibration.

Record while the example is running, then replay that archive with the same command. The archive must contain every source the command opens: `CAM_A`, plus the stereo cameras `Depth` opens (`CAM_B` and `CAM_C` on an OAK-D). Extra streams are ignored. If a source is missing, the log says replay is disabled and the script uses the live cameras. A failed setup warns `Replay disabled` or `Could not set up holistic replay`. `Replay enabled` is an info line and stays hidden at the default log level.

```bash
mkdir -p recordings
DEPTHAI_RECORD="$PWD/recordings" python3 main.py
DEPTHAI_REPLAY="$PWD/recordings/recording_<time>.tar.gz" python3 main.py
```

Stop the recording with `q`. Do not set `DEPTHAI_RECORD` and `DEPTHAI_REPLAY` together. A device that can run this pipeline is still required. `camera_info.json` in the archive replaces the device calibration for that run. On RVC2 the recording is replayed on the host. On RVC4 each camera is replayed on the device. `oakctl app run` does not see these host environment variables.

The default recording is H.264, so a replayed measurement can differ slightly from the live run. Sequence numbers and device timestamps on the first pass are the recorded ones.

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
