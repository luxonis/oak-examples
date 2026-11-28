# Spatial detection fusion

This example demonstrates a multiple Luxonis OAK cameras setup that detects objects in 3D space, fuses the data from all connected cameras, and visualizes the results in a unified Bird's Eye View (BEV).

## Demo

The following GIF shows bird's-eye view of fused detections of label `person` from three cameras.

![demo](https://github.com/user-attachments/assets/6f92dc14-ebda-4bd1-a57e-cf5f1b24ea17)

## Usage

> Before you can run this demo you need to calibrate the cameras, the goal is to figure out the exact position and orientation of every camera relative to each other, so the application can fuse their individual views into a single, unified coordinate system. Go to [multi-device-calibration](../multi-device-calibration) and generate the calibration file for your devices. Once calibration is complete, do not move your cameras. If you do, you will need to re-calibrate. By default the file is read from `calibration.json` next to `main.py`: save it there with `python main.py -o ../spatial-detection-fusion/calibration.json` in the calibration example, or pass its path with `--calibration`.

The program prints the connected camera sockets for each device before starting the pipeline. Below is an example output:

```
=== Connected to device: 2727018817
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
=== Connected to device: 3121428587
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
Pipeline started with 2 devices.
```

Running this example requires at least two calibrated, stereo-capable **Luxonis devices** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-c, --calibration CALIBRATION
                      Calibration JSON saved by the multi-device-calibration example
                      (default: calibration.json next to main.py)
-d, --devices DEVICES [DEVICES ...]
                      Device IDs or IP addresses to use. If omitted, every device in the calibration is used.
--fps_limit FPS_LIMIT FPS limit for the model runtime (default: 30)
```

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python 3.12** environment (recommended) with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/)
- [NumPy](https://pypi.org/project/numpy/)
- [SciPy](https://pypi.org/project/scipy/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

### How it works

The example runs one `dai.Pipeline` across all devices:

- **Per device**: a `Camera`, a `Depth` node and a `SpatialDetectionNetwork` are created on the device with `pipeline.create(node, device)`. Each device reports `SpatialImgDetections` in the coordinate system of its own camera.
- **Shared calibration**: `pipeline.setMultiDeviceCalibration` loads the calibration graph, so the transformation attached to every message refers to one common origin.
- **Synchronization**: a host `Sync` node groups one detection message per device by timestamp.
- **Fusion**: the `FusionManager` host node moves all detections into the camera frame of the first device with `SpatialImgDetections.transformTo` and groups detections of the same label that are closer than `DISTANCE_THRESHOLD_M`.
- **Visualization**: the `BirdsEyeView` host node draws the top-down view of that frame: X to the right, the first camera's viewing direction up.

The first device should be mounted roughly level, because the bird's-eye view looks along its vertical axis. Settings are in [`utils/config.py`](utils/config.py).

### Examples

```bash
python main.py
```

This will run the demo with every device listed in the default calibration file.

```bash
python main.py --calibration /path/to/calibration.json
```

This will use the devices and poses from another calibration file.

```bash
python main.py --devices 192.168.1.10 192.168.1.11
```

This will use only the named devices; they must be part of the calibration. The first one defines the bird's-eye view.

```bash
python main.py --fps_limit 15
```

This will run the demo with an FPS limit of 15 for all cameras.
