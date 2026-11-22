# IMU Calibration

Guided six-pose IMU calibration for OAK devices, modeled after the [Intel RealSense D435i IMU calibration](https://www.realsenseai.com/wp-content/uploads/2019/07/Intel_RealSense_Depth_D435i_IMU_Calibration.pdf) procedure. The app walks you through six static poses, computes the IMU calibration, shows the result, and flashes it to the device EEPROM only after you confirm.

It computes and flashes:

- **IMU -> camera rotation** (`imuExtrinsics.rotationMatrix`), found from the measured gravity directions.
- **Accelerometer `[Q|b]`**: scale/misalignment correction and bias, applied after the rotation.
- **Gyroscope `[I|b]`**: static bias, applied after the rotation.
- **IMU -> camera translation** (`translation` and `specTranslation`), taken from the board design in [depthai-boards](https://github.com/luxonis/depthai-boards). A static procedure cannot measure the translation.

DepthAI applies the stored values as `calibrated = Q @ (R @ raw) + b`.

## Flow

1. For each of the six poses, place the device as shown in the photo and press `SPACE`. The device must stay still for the capture (4 s by default).
   - The app shows live whether the device is still and, from pose 2 on, whether the orientation is consistent with the poses captured so far.
   - A capture is rejected when the device moved or the orientation is wrong. Press `B` to go back and redo the previous pose.
2. The results screen shows the rotation (and whether it matches the depthai-boards design), `[Q|b]`, gyroscope bias, translation, and the worst per-pose error. Flashing is disabled when a sanity check fails.
3. Press `F` to flash. The previous EEPROM calibration is backed up to a JSON file first. Press `R` to redo the capture, `Q` to quit.

Every finished capture is saved as `imu_calibration_<timestamp>.json` in the output directory (pose means and computed matrices). Flashing only replaces the user calibration; the factory calibration stays on the device.

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

The board config is looked up by the product and board name stored in the device EEPROM. If the lookup fails (no network, unknown board), the app keeps the translation already in EEPROM and says so on the results screen. Pass `--board-config` to use a local depthai-boards checkout instead.

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [NumPy](https://pypi.org/project/numpy/),
- [OpenCV](https://pypi.org/project/opencv-python-headless/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

### Examples

```bash
python3 main.py
```

Then open the Visualizer link printed in the terminal (by default http://localhost:8082) and follow the instructions there. Key presses are read from the Visualizer.

```bash
python3 main.py --board-config ~/depthai-boards/boards/OAK-D-PRO.json
```

This uses a local board config instead of downloading depthai-boards.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).

In standalone mode the reports and EEPROM backups go to the app's persistent storage (`$OAKAGENT_STORAGE_APP/imu_calibration_output`), which survives app restarts and updates. The full path is printed after flashing; open a shell in the app with `oakctl app exec <app-id> -i /bin/bash` to read them.
