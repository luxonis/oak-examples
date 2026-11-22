# AGENTS.md

## Summary

This is the reference for guided on-device IMU calibration: a six-pose static capture with a custom frontend that computes the IMU -> camera rotation, accelerometer scale and bias, and gyroscope bias, previews them on live data, then flashes them with the depthai-boards IMU translation after user confirmation.

## Use This Example When

- You need to recalibrate or fix the IMU extrinsics rotation or accelerometer/gyroscope calibration stored in EEPROM.
- You want a custom frontend that plots live IMU data and drives a backend state machine through services, in both peripheral and standalone modes.
- You need to read or write IMU calibration through `CalibrationHandler`.

## Do Not Use This Example When

- You only need to read IMU data; start from a simpler IMU example instead.
- You need camera intrinsics/extrinsics or stereo calibration.
- You need IMU-camera translation or time-offset calibration; this static procedure cannot measure them.

## Quick Facts

- `Category:` `apps/imu-calibration`
- `Shape:` `frontend`
- `Primary task:` six-pose IMU calibration and EEPROM flashing
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` a device with an IMU and existing EEPROM calibration; a built frontend (`npm run build`) for peripheral mode; network access to GitHub for the depthai-boards lookup (optional)
- `Input:` `ACCELEROMETER_RAW`, `GYROSCOPE_RAW`, and `MAGNETOMETER_RAW` (when present) at 100 Hz; `CAM_A` camera
- `Output:` `Camera` topic (H.264), `IMU State` / `IMU Action` services, JSON reports and EEPROM backups in `--output-dir`, flashed calibration
- `Models:` none
- `Visualizer / UI:` custom React frontend using `@luxonis/depthai-viewer-common`; served by `main.py` on port 8082 in peripheral mode and by the OAK agent in standalone mode

## Read First

- [main.py](main.py): frontend server, device connection, mounting lookup, camera + IMU pipeline, service registration
- [utils/calibrator_node.py](utils/calibrator_node.py): capture state machine, `state()` / `action()` service handlers, report and flash
- [utils/calibration.py](utils/calibration.py): poses, least-squares fit, rotation extraction, sanity checks
- [utils/device_info.py](utils/device_info.py): device and stored-calibration summary
- [utils/board_config.py](utils/board_config.py): depthai-boards lookup and EEPROM fallback
- [frontend/src/App.tsx](frontend/src/App.tsx): polling, sample buffer, layout, stored vs new curves
- [frontend/src/api.ts](frontend/src/api.ts): service types, `applyCalibration`

## Architecture

- `IMU` streams raw samples into the `ImuCalibrator` threaded host node; `CAM_A` goes through a `VideoEncoder` (H.264) to the `Camera` topic.
- The frontend polls `IMU State` every 100 ms with `{since}` and gets the phase, pose status, device info, result, and RAW samples newer than `since` (every 4th packet, 25 Hz, 10 s buffer).
- Buttons call `IMU Action` with `capture`, `back`, `redo`, or `flash`.
- The frontend applies the stored calibration and the new result to the same RAW samples with `applyCalibration`, so stored vs new comparison never changes device state.
- After six accepted poses, `calibrate()` fits `targets = Q_total @ raw_mean + b` on per-pose means, splits `Q_total = Q @ R` with `R` the nearest proper signed permutation, and sets the gyro bias to `-R @ mean(raw_gyro)`.
- `ImuCalibrator._flash()` backs up the EEPROM JSON, calls `setAccelerometerCalibration`, `setGyroscopeCalibration`, `setImuExtrinsics`, and `flashCalibration`, then re-reads device info.

## Constraints

- DepthAI applies `calibrated = Q @ (R @ raw) + b` (plus sign); RAW streams are sensor-native since DepthAI 3.6. Fitting on non-RAW streams would bake the current extrinsics into the result.
- `setImuExtrinsics` rejects reflections, so `R` is restricted to det = +1.
- Pose targets in `POSES` are in the camera RDF frame and must match the photos in [frontend/public/poses](frontend/public/poses).
- Flashing is blocked when `ImuCalibration.problems` is non-empty.
- Service callbacks run on the RemoteConnection thread; all node state is guarded by one lock.
- Raw NV12 camera frames delayed IMU packets by about 2 s on RVC4 peripheral; keep the camera H.264-encoded.
- RVC4 reports the IMU as `accel`, so board sensor matching falls back to the first listed sensor (the accel/gyro chip). BMI270 has no magnetometer, so it is not enabled there.
- The frontend connects to the websocket on port 8765 of the page host; only one instance can run per host.

## Related Examples

- [custom-frontend/raw-stream](https://github.com/luxonis/oak-examples/tree/main/custom-frontend/raw-stream): minimal custom frontend with services
- [apps/p2p-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/p2p-measurement): frontend polling services at a high rate
- [depth-measurement/dynamic-calibration](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/dynamic-calibration): stereo recalibration with flashing

## Validation

- `Run:` `cd frontend && npm install && npm run build`, then `python3 main.py` (peripheral) or `oakctl app run .` (RVC4 standalone)
- `Success looks like:` the page shows the camera, moving IMU charts, and a filled device panel; captures advance through six poses; the results panel shows "All checks passed."; with the device still, the new `|gravity|` is about 9.81 m/s² and the new gyro means are about 0
- `Common failure meaning:` "Waiting for IMU data" for more than 10 s means the IMU is not streaming; "Wrong orientation" means the pose does not match the photo; an EEPROM-sourced translation means the depthai-boards lookup failed
