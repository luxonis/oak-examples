# Multi device calibration

This example estimates the relative poses of two or more OAK devices with the `MultiDeviceCalibration` node and saves them as one calibration file. Other multi-device examples, such as [spatial-detection-fusion](../spatial-detection-fusion), load that file to express data from all devices in one coordinate system.

No calibration target is needed. The node matches image features of the scene that the cameras share:

1. **One pipeline for all devices**: a single `dai.Pipeline` spans every device; each `Camera` node is created on its device with `pipeline.create(dai.node.Camera, device)`.
2. **Synchronized samples**: full-resolution frames from all calibration cameras are grouped and collected.
3. **Pose estimation**: the node solves the pose of every device relative to one automatically selected origin device.
4. **Metric scale**: a factory-calibrated stereo pair (`CAM_B`/`CAM_C`) on any device fixes the scale. If no device has a stereo pair, pass the measured distance between the first two devices with `--known-distance`.
5. **Saving**: the result is written as JSON by `MultiDeviceCalibrationHandler`.

## Demo

Example output for two OAK4 devices mounted about 30 cm apart:

```
=== Device 2727018817: calibrating with CAM_B, CAM_C
=== Device 3121428587: calibrating with CAM_B, CAM_C
Open http://localhost:8082, aim all cameras at a shared textured scene and keep them still. Press 'c' to calibrate, 'q' to quit.
Collecting 10 synchronized samples...
Calibration saved to calibration.json
Confidence: 0.844, Sampson error: 0.0004021
  2727018817 CAM_A -> origin 2727018817: x=0.0 cm, y=0.0 cm, z=0.0 cm
  3121428587 CAM_A -> origin 2727018817: x=30.5 cm, y=1.4 cm, z=-4.5 cm
Press 'c' to calibrate again or 'q' to quit.
```

## Usage

Running this example requires at least two **Luxonis devices** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your devices if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d, --devices DEVICES [DEVICES ...]
                      Device IDs or IP addresses to calibrate. If omitted, the devices are discovered.
--include-ip          Also include IP-only cameras (e.g. OAK-4) when discovering devices
--max-devices MAX_DEVICES
                      Limit the number of discovered devices to this count
-n, --sample-count SAMPLE_COUNT
                      Number of synchronized image groups collected before solving (default: 10)
--known-distance KNOWN_DISTANCE
                      Measured distance in centimeters between the calibration cameras of the first two
                      devices. Required when no device has a CAM_B/CAM_C stereo pair.
-o, --output OUTPUT   Where to save the calibration JSON (default: calibration.json next to main.py)
```

### Controls

| Key | Action                                                                                                |
| :-- | :---------------------------------------------------------------------------------------------------- |
| `c` | **Calibrate**: collects synchronized samples, solves the device poses and saves the calibration file. |
| `q` | **Quit**: stops the pipeline and exits the application.                                               |

#### Step-by-Step Guide for Accurate Calibration

1. **Mount the devices**\
   Fix all devices in their final positions. The calibration is valid only as long as the devices do not move relative to each other.

2. **Share the scene**\
   Open the Visualizer and check the previews. The cameras must see a common, textured, well-lit and static scene. Blank walls, strong backlight and moving objects make the calibration fail.

3. **Start Calibration**\
   Press the `c` key. Progress, the confidence of the result and errors are printed in your terminal. Press `c` again to retry.

4. **Verify Saved Output**\
   The terminal prints the position of every device relative to the origin device. Compare it with your physical setup. The calibration is saved to `calibration.json` unless `--output` says otherwise.

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python 3.12** environment (recommended) with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

#### Examples

```bash
python main.py
```

This will calibrate all discovered USB devices.

```bash
python main.py --include-ip --max-devices 3
```

This will also discover TCP/IP cameras on the network and calibrate the first 3 discovered devices.

```bash
python main.py --devices 192.168.1.10 192.168.1.11
```

This will calibrate exactly the two named devices. Prefer this on a network with many cameras.

```bash
python main.py --devices 192.168.1.10 192.168.1.11 --known-distance 25
```

This will calibrate two single-camera devices whose cameras are 25 cm apart.
