# Multi device box measurement

This example measures the length, width and height of boxes seen by one or more OAK 4 devices. Devices placed around a scene see different sides of the same box, and the example combines them into one measurement per box. The surface the boxes stand on, the support plane, is found automatically.

How it works:

1. **Multi-device calibration**: with two or more devices, the `MultiDeviceCalibration` node estimates the pose of every device relative to one origin device (first run only). One device needs no multi-device calibration.
2. **Per device**: a color camera and a `Depth` node aligned to it are created on the device. With two or more devices, the devices capture at unrelated times, and the frames of all devices are grouped within half a frame period. With `--ptp`, all cameras capture on the PTP clock, so the frames of all devices are taken at the same time.
3. **Support plane**: one host `PointCloud` node merges the depth of all devices in millimeters. The [`AutoSupportPlane`](https://github.com/luxonis/depthai-nodes/tree/main/depthai_nodes/node/support_plane_calibrator) node from depthai-nodes fits planes to it and keeps the one that is perpendicular to the gravity from the first device's IMU. It checks the plane again about every 0.5 s and finds it again when it no longer fits, for example after a device moves.
4. **Measurement**: the `BoxMeasurer` node from depthai-nodes detects boxes on each device with the `luxonis/box-instance-segmentation` model, joins the views of the same box and measures it against the support plane.

## Demo

<!-- TODO: Add a compact screenshot or GIF of the Visualizer with measured boxes from two devices, stored in media/. -->

## Usage

Running this example requires one or more **OAK 4** devices with a color camera and a stereo pair, such as OAK 4 D. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your devices if you haven't done it already.

With two or more devices, also make sure that:

- The devices see a shared, textured, static scene for the multi-device calibration.
- To measure moving boxes, for example on a conveyor, pass `--ptp`. The devices must then be on an Ethernet network that supports PTP, and run Luxonis OS 1.35.0 or newer. Refer to the [PTP documentation](https://docs.luxonis.com/hardware/platform/deploy/data-sync/ptp-sync). Without PTP, only static boxes are measured correctly: a moving box is at a different position in each view, and it can be split into two boxes or measured too large.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

### Multi-device calibration

With two or more devices, the example needs their relative poses. On the first run it calibrates them with the `MultiDeviceCalibration` node and saves the result to `calibration.json`; later runs reuse the file.

- Mount the devices in their final positions and aim them at a shared, textured, static scene before the first run.
- Pass `--calibrate` after moving a device, or `--calibration` to reuse a file from [multi-device-calibration](https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multi-device-calibration).

The support plane is found again on every start, and whenever it no longer fits. Keep most of it free of boxes while the example searches for it.

Here is a list of all available parameters:

```
-d, --devices DEVICES [DEVICES ...]
                      Device IDs or IP addresses to use. If omitted, the devices are discovered.
--include-ip          Also include IP-only cameras (e.g. OAK-4) when discovering devices
--max-devices MAX_DEVICES
                      Limit the number of discovered devices to this count
-c, --calibration CALIBRATION
                      Multi-device calibration JSON. It is created on the first run with two or
                      more devices. (default: calibration.json next to main.py)
--calibrate           Run the multi-device calibration again even if the calibration file exists
-n, --sample-count SAMPLE_COUNT
                      Number of synchronized image groups collected for the multi-device calibration (default: 10)
--ptp                 Capture on the PTP clock, so that moving boxes are measured correctly.
                      Without it, the frames of all devices are grouped within half a frame
                      period, and only static boxes are measured correctly.
--fps_limit FPS_LIMIT FPS limit of the cameras. (default: 10)
```

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python >= 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/) with the `box-measurement` extra (installs open3d)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

#### Examples

```bash
python main.py --devices 192.168.1.10 192.168.1.11
```

This will calibrate the two named devices on the first run and then start measuring static boxes. Prefer `--devices` on a network with many cameras.

```bash
python main.py --include-ip --max-devices 2
```

This will discover USB and TCP/IP cameras and use the first 2 discovered devices. OAK 4 devices connect over TCP/IP, so discovery without `--include-ip` does not find them.

```bash
python main.py --devices 192.168.1.10 192.168.1.11 --ptp
```

This will measure with two devices on the PTP clock, so that moving boxes are measured correctly.

```bash
python main.py --devices 192.168.1.10
```

This will measure with one device, without multi-device calibration and PTP.

```bash
python main.py --devices 192.168.1.10 192.168.1.11 --calibrate
```

This will redo the multi-device calibration, for example after a device was moved.
