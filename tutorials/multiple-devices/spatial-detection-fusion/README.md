# Spatial detection fusion

This example demonstrates a multiple Luxonis OAK cameras setup that detects objects in 3D space, fuses the data from all connected cameras, and visualizes the results in a unified Bird's Eye View (BEV).

## Demo

The following GIF shows bird's-eye view of fused detections of label `person` from three cameras.

![demo](https://github.com/user-attachments/assets/6f92dc14-ebda-4bd1-a57e-cf5f1b24ea17)

## Usage

> Before you can run this demo you need to calibrate the cameras, the goal is to figure out the exact position and orientation of every camera relative to each other, so the application can fuse their individual views into a single, unified "world". Go to [multi-cam-calibration](../multi-cam-calibration) and generate a calibration file for each camera. Once calibration is complete, do not move your cameras. If you do, you will need to re-calibrate. Make sure that the `calibration_data_dir` in the [`config.py`](config.py) is set correctly.

The program will also print the USB speed and connected camera sockets for each connected device before starting its pipeline. Below is an example output:

```
Found 2 DepthAI devices to configure.
✅ Loaded extrinsics for 14442C1011D6C5D600 (Friendly ID: 1)
✅ Loaded extrinsics for 19443010F1E61F1300 (Friendly ID: 2)
Proceeding with 2 devices that have extrinsics.

Successfully connected to device 14442C1011D6C5D600 for main pipeline.

Skipping initialization of device 14442C1011D6C5D600 as it is already initialized.
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
        Pipeline for 14442C1011D6C5D600 configured. Ready to be started.

Attempting to connect to device: 19443010F1E61F1300...
=== Successfully connected to device: 19443010F1E61F1300
    >>> Pipeline created for device: 19443010F1E61F1300
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
        Pipeline for 19443010F1E61F1300 configured. Ready to be started.

```

Running this example requires at least one (or multiple) **Luxonis device(s)** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
--include-ip                   Also include IP-only cameras (e.g. OAK-4) in the device list
--max-devices MAX_DEVICES      Limit the total number of devices to this count
--fps_limit FPS_LIMIT          FPS limit for the model runtime (default: 30)
```

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

The system employs a *main device* architecture. Upon launch, the first available OAK device is designated as the central communication hub.

- **Main Device**: This camera is responsible for more than just its own detections, it also facilitates the communication of the `HostNode`s (`FusionManager` and `BirgsEyeView`).

- **Secondary Devices**: All other connected cameras act as secondary data sources. They perform their own spatial detection and then stream their results directly to the `FusionManager` running on the main device's pipeline.

### Examples

```bash
python main.py
```

This will run the demo using only internal DepthAI cameras.

```bash
python main.py --include-ip
```

This will also discover and use any TCP/IP cameras on the network.

```bash
python main.py --max-devices 3
```

This will stop after configuring the first 3 devices.

```bash
python main.py --include-ip --max-devices 3
```

This will include IP cameras and then only use the first 3 discovered devices.

```bash
python main.py --fps_limit 30
```

This will run the demo with an FPS limit of 30 for all cameras.
