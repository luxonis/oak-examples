# Multi device panorama

This example calibrates two or more OAK devices and composes their color cameras into one panorama with the `Stitching` node. A single `dai.Pipeline` spans all devices, and the panorama is composed from the calibrated camera poses instead of from image features.

How it works:

1. **Calibration**: the `MultiDeviceCalibration` node estimates the pose of every device relative to one origin device (first run only).
2. **Shared coordinate system**: `pipeline.setMultiDeviceCalibration` applies the calibration, so the transformation attached to every frame refers to the common origin.
3. **Per device**: a `Camera` is created on the device with `pipeline.create(dai.node.Camera, device)` and sends an undistorted `1280x800` view to the host.
4. **Stitching**: one host `Stitching` node in `PANORAMA` mode with `setUseInputCalibration(True)` renders all views onto a cylinder, a sphere or a plane (`--projection`).

A panorama is exact only for cameras that share one optical center. Devices mounted apart see near objects from different directions, so objects close to the cameras can be cut or doubled at the seam; distant scenery lines up.

## Demo

The Visualizer shows the undistorted input of every device and the `Panorama` topic.

## Usage

Running this example requires at least two **Luxonis devices** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your devices if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

### Calibration

The example needs the relative poses of the devices. On the first run it calibrates them with the `MultiDeviceCalibration` node and saves the result to `calibration.json`; later runs reuse the file.

- Mount the devices in their final positions and aim them at a shared, textured, static scene before the first run.
- A factory-calibrated stereo pair (`CAM_B`/`CAM_C`) on any device fixes the metric scale. If no device has one, pass the measured distance between the first two devices with `--known-distance`.
- Pass `--calibrate` after moving a device, or `--calibration` to reuse a file from [multi-device-calibration](../multi-device-calibration).

Here is a list of all available parameters:

```
-d, --devices DEVICES [DEVICES ...]
                      Device IDs or IP addresses to use. If omitted, the devices are discovered.
--include-ip          Also include IP-only cameras (e.g. OAK-4) when discovering devices
--max-devices MAX_DEVICES
                      Limit the number of discovered devices to this count
-c, --calibration CALIBRATION
                      Multi-device calibration JSON. It is created on the first run.
                      (default: calibration.json next to main.py)
--calibrate           Calibrate again even if the calibration file exists
-n, --sample-count SAMPLE_COUNT
                      Number of synchronized image groups collected for the calibration (default: 10)
--known-distance KNOWN_DISTANCE
                      Measured distance in centimeters between the calibration cameras of the first two
                      devices. Required when no device has a CAM_B/CAM_C stereo pair.
--fps_limit FPS_LIMIT FPS limit of the cameras. (default: 15)
--projection {Cylindrical,Equirectangular,Perspective}
                      Surface the panorama is rendered on (default: Cylindrical)
--no-blend            Disable seam finding and blending; faster, with visible seams
```

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python >= 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

#### Examples

```bash
python main.py --devices 192.168.1.10 192.168.1.11
```

This will calibrate the two named devices on the first run and then start the example. Prefer `--devices` on a network with many cameras.

```bash
python main.py --include-ip --max-devices 3
```

This will discover USB and TCP/IP cameras and use the first 3 discovered devices.

```bash
python main.py --devices 192.168.1.10 192.168.1.11 --calibrate
```

This will redo the calibration, for example after a device was moved.
