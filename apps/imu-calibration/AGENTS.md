# AGENTS.md

## Summary

This is the reference for guided on-device IMU calibration: a six-pose static capture that computes the IMU -> camera rotation, accelerometer scale and bias, and gyroscope bias, then flashes them with the depthai-boards IMU translation after user confirmation.

## Use This Example When

- You need to recalibrate or fix the IMU extrinsics rotation or accelerometer/gyroscope calibration stored in EEPROM.
- You want a pattern for a guided, key-driven Visualizer workflow that renders its own UI frames from a host node.
- You need to read or write IMU calibration through `CalibrationHandler`.

## Do Not Use This Example When

- You only need to read IMU data; start from a simpler IMU example instead.
- You need camera intrinsics/extrinsics or stereo calibration.
- You need IMU-camera translation or time-offset calibration; this static procedure cannot measure them.

## Quick Facts

- `Category:` `apps/imu-calibration`
- `Shape:` `script+standalone`
- `Primary task:` six-pose IMU calibration and EEPROM flashing
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` a device with an IMU and existing EEPROM calibration; network access to GitHub for the depthai-boards lookup (optional)
- `Input:` `ACCELEROMETER_RAW` and `GYROSCOPE_RAW` at 100 Hz, Visualizer key presses
- `Output:` `IMU Calibration` guide frames, JSON reports and EEPROM backups in `--output-dir`, flashed calibration
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`; keys `SPACE`, `B`, `F`, `R`, `Q`

## Read First

- [main.py](main.py): device connection, mounting lookup, IMU node, key forwarding
- [utils/calibration.py](utils/calibration.py): poses, least-squares fit, rotation extraction, sanity checks
- [utils/calibrator_node.py](utils/calibrator_node.py): capture state machine, rendering, flashing
- [utils/board_config.py](utils/board_config.py): depthai-boards lookup and EEPROM fallback

## Architecture

- `IMU` node streams raw accelerometer and gyroscope samples into the `ImuCalibrator` threaded host node.
- The main thread reads keys with `RemoteConnection.waitKey` and forwards them to the node through a queue; `q` stops the app.
- The node renders 1280x720 NV12 guide frames at 15 FPS to the `IMU Calibration` topic.
- After six accepted poses, `calibrate()` fits `targets = Q_total @ raw_mean + b` on per-pose means, splits `Q_total = Q @ R` with `R` the nearest proper signed permutation, and sets the gyro bias to `-R @ mean(raw_gyro)`.
- `ImuCalibrator._flash()` backs up the EEPROM JSON, then calls `setAccelerometerCalibration`, `setGyroscopeCalibration`, `setImuExtrinsics`, and `flashCalibration`.

## Constraints

- DepthAI applies `calibrated = Q @ (R @ raw) + b` (plus sign); RAW streams are sensor-native since DepthAI 3.6. Fitting on non-RAW streams would bake the current extrinsics into the result.
- `setImuExtrinsics` rejects reflections, so `R` is restricted to det = +1.
- Pose targets in `POSES` are in the camera RDF frame and must match the photos in [assets/poses](assets/poses).
- Flashing is blocked when `ImuCalibration.problems` is non-empty.
- RVC4 reports the IMU as `accel`, so board sensor matching falls back to the first listed sensor (the accel/gyro chip).

## Related Examples

- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): baseline Visualizer app shell
- [depth-measurement/dynamic-calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): stereo recalibration with key-driven flashing

## Validation

- `Run:` `python3 main.py` (peripheral) or `oakctl app run .` (RVC4 standalone)
- `Success looks like:` the Visualizer shows the pose-1 guide with "Device is still.", captures advance through six poses, and the results screen shows "All checks passed." with a rotation that matches depthai-boards
- `Common failure meaning:` "Wrong orientation" means the pose does not match the photo; "differs from depthai-boards spec" means the stored rotation was wrong or the poses were mirrored; an EEPROM-sourced translation means the depthai-boards lookup failed
