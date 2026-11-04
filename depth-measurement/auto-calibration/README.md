# Stereo Automatic Calibration

This example runs `dai.node.AutoCalibration` with live stereo/depth previews and a status HUD in the DepthAI Visualizer. It is a separate, automatically managed workflow alongside the [Dynamic Calibration example](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration), which provides manual coverage, quality, apply/revert, and flash controls.

## Features

- On-start validation and recalibration, or continuous cycles with a configurable pause.
- `Left`, `Right`, and `Depth` views, with an `AutoCalib HUD` annotation layer.
- Validation status, data/calibration confidence, and parameter-change status in the HUD and console JSON.
- Runtime calibration updates only: `flashCalibration=False` is set explicitly. This example has no flash controls and never deliberately perturbs calibration.

## Requirements

Use Python 3.10 or later and a supported OAK device with calibrated stereo cameras on `CAM_B/C`. Both sensors must support matching native **1280×800 or 640×400** modes. The script checks available sensor modes before starting and prefers 1280×800.

```bash
pip install -r requirements.txt
```

## Peripheral Mode

```bash
python3 main.py
python3 main.py --device <DEVICE_IP_OR_ID>
python3 main.py --mode continuous --auto-interval 30 --device <DEVICE_IP_OR_ID>
```

Open the Visualizer URL printed by the application. `AutoCalib HUD` belongs to the same image group as the stereo/depth previews. Press `q` in the Visualizer to quit.

| Argument | Default | Meaning |
| --- | --- | --- |
| `-d`, `--device` | First available device | Device name, ID, or IP address |
| `-fps`, `--fps_limit` | `10` | Positive stereo camera FPS limit |
| `--mode` | `on-start` | `on-start` or `continuous` |
| `--auto-interval` | `30` | Positive pause in seconds after each continuous cycle |

## Calibration Behavior

AutoCalibration owns its internal DynamicCalibration worker and samples unrectified camera ISP frames. The same camera pair feeds `StereoDepth`; the `Depth` preview displays colorized disparity.

Native acceptance rules remain enabled: five validation images, calibration confidence above `0.9`, the SDK's lens-specific data-confidence threshold, and up to five iterations. Poor scene coverage or texture can cause retries or unsuccessful cycles. The HUD shows the latest completed result while another continuous cycle runs.

A passed result can validate the existing parameters without changing them. Accepted calibration changes are applied by the SDK to runtime device geometry. A failed result leaves the active calibration unchanged. DepthAI 3.11 reports zero confidence fields on final failure; use SDK info logs (`DEPTHAI_LEVEL=info`) to inspect individual retries.

Automatic calibration never writes EEPROM here, and runtime changes disappear after device restart. The SDK's implicit pipeline calibration procedure is disabled so it cannot run alongside this explicit node. Use the separate manual Dynamic Calibration example when you need diagnostic commands or an explicit persistence workflow.

DepthAI 3.11 cannot publish `AutoCalibrationResult` directly through RemoteConnection. The small host status node converts results into HUD annotations and console JSON; it does not apply or flash calibration.

## Standalone Mode (RVC4 Only)

```bash
oakctl app run . -d <DEVICE_IP_OR_ID>
```

The packaged entrypoint uses on-start mode. To change the mode or interval, add the corresponding arguments to `entrypoint` in `oakapp.toml` before packaging. RVC2 devices use peripheral mode.

## Related Examples

- [Dynamic Calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): interactive manual calibration, coverage/quality inspection, apply/revert, and explicit flashing.
- [Stereo Runtime Configuration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/stereo-runtime-configuration): adjust stereo matching parameters while streaming.
