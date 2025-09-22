# Multiple devices per host

This example demonstrates how to connect and use multiple DepthAI (OAK) devices simultaneously on a single host machine. Each connected device will initialize a pipeline, and an RGB preview from each will be displayed independently.

This tutorial contains three main scripts:

1. [main.py](main.py) – Displays RGB previews from multiple connected devices.
2. [multi-device-yolov6.py](multi-device-yolov6.py) – Runs YOLOv6 object detection on all devices.
3. [multi-device-encoding.py](multi-device-encoding.py) – Streams and decodes H.264 video from all devices.

## Demo

![demo_1](https://github.com/user-attachments/assets/6f5e913d-2b25-4f46-b77a-7c0a89821caf)

Just two OAK cameras looking at each other.

Program will also print USB speed, and connected cameras for each connected device before starting the pipeline. Output example for having connected OAK-D S2, OAK-D PRO

```
Found 2 DepthAI devices to configure.

Attempting to connect to device: 19443010F1E61F1300...
=== Successfully connected to device: 19443010F1E61F1300
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
    Pipeline created for device: 19443010F1E61F1300
    Pipeline for 19443010F1E61F1300 configured. Ready to be started.

Attempting to connect to device: 14442C1011D6C5D600...
=== Successfully connected to device: 14442C1011D6C5D600
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
    Pipeline created for device: 14442C1011D6C5D600
    Pipeline for 14442C1011D6C5D600 configured. Ready to be started.

```

## Usage

Running this example requires at least one (or multiple) **Luxonis device(s)** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
--include-ip          Also include IP-only cameras (e.g. OAK-4) in the device list
--max-devices MAX_DEVICES
                        Limit the total number of devices to this count
```

### Peripheral Mode

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app.
You can find more information about the supported devices and the set up instructions in our [Documentation](https://rvc4.docs.luxonis.com/hardware).
Moreover, you need to prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

#### Examples

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

#### Object detection on multiple devices

Script [multi-device-yolov6.py](multi-device-yolov6.py) will run `YOLOv6 Nano` single shot object detector on all devices and display detections on frames.
If you would want to display detections on high-res frames, check [tutorial here](https://docs.luxonis.com/projects/api/en/latest/tutorials/dispaying_detections/).

![demo_2](https://github.com/user-attachments/assets/a700342c-2105-40b0-a831-66efb094b19c)

Run this script with

```bash
python3 multi-device-yolov6.py [--include-ip] [--max-devices N]
```

#### H.264 encoding on multiple devices

The [multi-device-encoding.py](multi-device-encoding.py) script will connect to multiple devices and stream encoded H.264 frames from all devices to the host. On host computer we run a thread for each device, boot the device, get frames, decode them, and put them in a queue which the main thread reads and displays the frame on the main thread.

Run this script with

```bash
python3 multi-device-encoding.py [--include-ip] [--max-devices N]
```
