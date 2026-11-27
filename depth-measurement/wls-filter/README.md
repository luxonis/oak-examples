## Host-Side WLS Filtering

This example applies host-side WLS filtering to stereo disparity, using the rectified right image as guidance, and converts the result to depth in millimeters.

On RVC2, post-processing can normalize disparity beyond its subpixel precision. The conversion includes this normalization and uses the disparity frame's intrinsics for the configured CAM_C alignment.

## Demo

<img width="1239" alt="Screenshot 2025-05-02 at 13 46 15" src="https://github.com/user-attachments/assets/57f2f66e-a0a3-44b3-bb88-a2ae4a8c6e93" />

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
```

Use the following keyboard controls in the visualizer to adjust WLS filtering parameters:

| Key | Action            |
| --- | ----------------- |
| `l` | Decrease lambda   |
| `L` | Increase lambda   |
| `s` | Decrease sigma    |
| `S` | Increase sigma    |
| `q` | Quit the pipeline |

- **Lambda** controls the amount of smoothing (higher = smoother).
- **Sigma** controls the edge sensitivity (higher = more edge-aware).

## Holistic replay

Replay is optional. The host WLS filter stays. The archive must contain `CAM_B` and `CAM_C`, so both the device disparity and the filtered view are computed from the same recorded pair. A failed setup warns `Replay disabled` or `Could not set up holistic replay`. `Replay enabled` is an info line and stays hidden at the default log level.

```bash
mkdir -p recordings
DEPTHAI_RECORD="$PWD/recordings" python3 main.py
DEPTHAI_REPLAY="$PWD/recordings/recording_<time>.tar.gz" python3 main.py
```

Stop the recording with `q`. Do not set `DEPTHAI_RECORD` and `DEPTHAI_REPLAY` together. A device that can run `StereoDepth` is still required. `camera_info.json` replaces the device calibration for that run, including the baseline this example reads. On RVC2 the recording is replayed on the host. On RVC4 each camera is replayed on the device. `oakctl app run` does not see these host environment variables.

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
