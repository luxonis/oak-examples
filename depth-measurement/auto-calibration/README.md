# Stereo Automatic Calibration

This example runs `dai.node.AutoCalibration` with live stereo/depth previews and a status HUD in the DepthAI Visualizer. It is a separate, automatically managed workflow alongside the [Dynamic Calibration example](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration), which provides manual coverage, quality, apply/revert, and flash controls.

## Features

- On-start validation and recalibration, or continuous cycles with a configurable pause.
- `Left`, `Right`, and `Depth` views, with an `AutoCalib HUD` annotation layer.
- Validation status, data/calibration confidence, and parameter-change status in the HUD and console JSON.
- Runtime calibration updates only: `flashCalibration=False` is set explicitly. This example has no flash controls and never deliberately perturbs calibration.

## Usage

Running this example requires a **Luxonis device** with calibrated stereo cameras on `CAM_B/C` connected to your computer. Both sensors must support matching native **1280×800 or 640×400** modes; the script checks available sensor modes before starting and prefers 1280×800. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional device name, ID or IP address. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    Stereo camera FPS limit. (default: 10)
--mode {on-start,continuous}
                    When to run automatic calibration. Updates stay in RAM. (default: on-start)
--auto-interval AUTO_INTERVAL
                    Seconds to pause after each continuous calibration cycle. (default: 30)
```

Open the Visualizer URL printed by the application. `AutoCalib HUD` belongs to the same image group as the stereo/depth previews. Press `q` in the Visualizer to quit.

### Calibration Behavior

AutoCalibration owns its internal DynamicCalibration worker and samples unrectified camera ISP frames. The same camera pair feeds `StereoDepth`; the `Depth` preview displays colorized disparity.

Native acceptance rules remain enabled: five validation images, calibration confidence above `0.9`, the SDK's lens-specific data-confidence threshold, and up to five iterations. Poor scene coverage or texture can cause retries or unsuccessful cycles. The HUD shows the latest completed result while another continuous cycle runs.

A passed result can validate the existing parameters without changing them. Accepted calibration changes are applied by the SDK to runtime device geometry. A failed result leaves the active calibration unchanged. DepthAI 3.12 reports zero confidence fields on final failure; use SDK info logs (`DEPTHAI_LEVEL=info`) to inspect individual retries.

Automatic calibration never writes EEPROM here, and runtime changes disappear after device restart. The SDK's implicit pipeline calibration procedure is disabled so it cannot run alongside this explicit node. Use the separate manual Dynamic Calibration example when you need diagnostic commands or an explicit persistence workflow.

DepthAI 3.12 cannot publish `AutoCalibrationResult` directly through RemoteConnection. The small host status node converts results into HUD annotations and console JSON; it does not apply or flash calibration.

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.12** environment (recommended) with the following packages installed:

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

This will run the example with the default device and a single on-start calibration cycle.

```bash
python3 main.py --mode continuous --auto-interval 30 --device <DEVICE_IP_OR_ID>
```

This will run calibration cycles continuously on the selected device, pausing 30 seconds after each cycle.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values (on-start mode). If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).

## Related Examples

- [Dynamic Calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): interactive manual calibration, coverage/quality inspection, apply/revert, and explicit flashing.
- [Stereo Runtime Configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): adjust stereo matching parameters while streaming.
