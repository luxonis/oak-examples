# IMU Calibration

Guided six-pose IMU calibration for OAK devices, with the same poses as the [Intel RealSense D435i IMU calibration](https://www.realsenseai.com/wp-content/uploads/2019/07/Intel_RealSense_Depth_D435i_IMU_Calibration.pdf). The app walks you through six static poses, computes the IMU calibration, previews it on live data next to the calibration stored on the device, and flashes it to the device EEPROM only after you confirm.

It computes and flashes:

- **IMU -> camera rotation** (`imuExtrinsics.rotationMatrix`), found from the measured gravity directions.
- **Accelerometer `[Q|b]`**: per-axis scale and bias, applied after the rotation. They are fitted so that gravity has the same magnitude (9.81 m/s²) in every pose. The poses do not have to be exactly axis-aligned, so holding the device a few degrees off does not bias the result.
- **Gyroscope `[I|b]`**: static bias, applied after the rotation.
- **IMU -> camera translation** (`translation` and `specTranslation`), taken from the board design in [depthai-boards](https://github.com/luxonis/depthai-boards). A static procedure cannot measure the translation.

DepthAI applies the stored values as `calibrated = Q @ (R @ raw) + b`.

## User Interface

The app has its own web frontend:

- **Center: live data.**
  - The camera stream, so you can see the app is not lagging.
  - Live charts of the accelerometer, gyroscope, and magnetometer (x/y/z).
  - After the results, the accelerometer and gyroscope charts show the **stored** calibration (dashed) and the **new** calibration (solid) on the same samples. Switches toggle each one.
- **Right sidebar: calibration.**
  - **Pose:** the photo and instructions for the current pose, live status ("Device is still", orientation check), and **Capture** / **Back** buttons.
  - **Results:** after six poses, this shows the sanity checks, the rotation (and whether it matches the depthai-boards design), `[Q|b]`, gyroscope bias, per-pose tilt, and **Flash to device** / **Redo**.
  - **Live check:** the mean of the last second of `|g|` (target 9.81 m/s²) and of the gyroscope per axis (target 0). It shows the calibration stored on the device next to the new one. After calibrating, tilt the device to any angle: the new `|g|` should stay at 9.81 m/s².
- **Left sidebar: device.** Device name and ID, platform, product, board, detected IMU and its firmware, magnetometer presence, and whether the IMU extrinsics, accelerometer calibration, and gyroscope calibration are missing, default, or calibrated in EEPROM.

## Flow

1. For each of the six poses, place the device as shown in the photo and press **Capture**. The device must stay still for the capture (4 s by default). A capture is rejected when the device moved or the orientation does not match the poses captured so far. **Back** redoes the previous pose.
2. Check the results and the live preview. Flashing is disabled when a sanity check fails.
3. Press **Flash to device**. The previous EEPROM calibration is backed up to a JSON file first. Flashing only replaces the user calibration; the factory calibration stays on the device. After flashing, the stored and new curves coincide.

Every finished capture is saved as `imu_calibration_<timestamp>.json` in the output directory (pose means and computed matrices).

## Usage

Running this example requires a **Luxonis device with an IMU** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
--board-config BOARD_CONFIG
                      Local depthai-boards board JSON (e.g. boards/OAK-D-PRO.json). By default it is looked up on GitHub. (default: None)
--capture-seconds CAPTURE_SECONDS
                      Capture duration per pose. (default: 4.0)
--output-dir OUTPUT_DIR
                      Directory for calibration reports and EEPROM backups. (default: imu_calibration_output, or $OAKAGENT_STORAGE_APP/imu_calibration_output in standalone mode)
```

The board config is looked up by the product and board name stored in the device EEPROM. If the lookup fails (no network, unknown board), the app keeps the translation already in EEPROM and shows the source in the device panel. Pass `--board-config` to use a local depthai-boards checkout instead.

## Peripheral Mode

### Installation

You need a **Python >= 3.10** environment with the backend dependencies:

```bash
pip install -r requirements.txt
```

and [Node.js](https://nodejs.org/en/download/) to build the frontend once:

```bash
cd frontend
npm install
npm run build
```

### Examples

```bash
python3 main.py
```

Then open http://localhost:8082 in your browser.

```bash
python3 main.py -d <DEVICE_ID_OR_IP> --board-config ~/depthai-boards/boards/OAK-D-PRO.json
```

This connects to a specific device and uses a local board config instead of downloading depthai-boards.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

The frontend is built inside the app container. This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).

In standalone mode the reports and EEPROM backups go to the app's persistent storage (`$OAKAGENT_STORAGE_APP/imu_calibration_output`), which survives app restarts and updates. The full path is shown after flashing; open a shell in the app with `oakctl app exec <app-id> -i /bin/bash` to read them.
