# Multi device bird's-eye view

This example calibrates two or more OAK devices, finds the ground in their merged point cloud and projects the left stereo camera of every device onto it with the `Stitching` node. The result is a metric top-down view of the floor composed from every device.

How it works:

1. **Calibration**: the `MultiDeviceCalibration` node estimates the pose of every device relative to one origin device (first run only).
2. **Merged point cloud**: a first pipeline runs a `Depth` node on every device and one host `PointCloud` node that merges them in the common calibration origin.
3. **Ground plane**: a RANSAC fit in [utils/plane.py](utils/plane.py) finds the largest roughly horizontal plane in that cloud.
4. **Planar projection**: a second pipeline sends an undistorted `CAM_B` frame at the sensor's native size from every device to one host `Stitching` node in `PLANAR_PROJECTION` mode; `setPlane` receives the fitted plane, which is expressed in the same origin frame as the camera transformations.

Only the ground is correct in the result. Everything that rises above the floor, such as people or furniture, is smeared away from the cameras.

## Demo

The terminal reports the fitted plane before the second pipeline starts:

```
Fitting the ground plane to the merged point cloud...
Ground plane: 37% of the points, origin camera 0.88 m above it, normal [0.02, -1.00, -0.02]
```

The Visualizer then shows a preview of every device and the `Birds-eye view` topic.

The view is grayscale because `CAM_B` is a monochrome stereo camera on most devices. The projection input has to be at the sensor's native size: on depthai 3.12 the node rejects most of a resized camera output, and the native size of a color `CAM_A` is too large to stream.

The devices must see the floor and be mounted roughly upright: the ground is searched among planes within 45° of the vertical axis of the origin camera.

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
--fps_limit FPS_LIMIT FPS limit of the cameras. (default: 10)
--max-range MAX_RANGE Distance in meters from the origin device beyond which the ground is not drawn (default: 4.0)
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
