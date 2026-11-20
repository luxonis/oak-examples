# Multiple devices per host

This example demonstrates how to use multiple DepthAI (OAK) devices simultaneously from a single host machine. One `dai.Pipeline` spans all devices: every device is added with `pipeline.addDevice` and its nodes are created on it with `pipeline.create(node, device)`.

This tutorial contains three main scripts:

1. [main.py](main.py) – Displays RGB previews from multiple connected devices.
2. [multi-device-yolov6.py](multi-device-yolov6.py) – Runs YOLOv6 object detection on all devices.
3. [multi-device-encoding.py](multi-device-encoding.py) – Streams H.264 video from all devices.

The part shared by all three scripts is in [utils/utility.py](utils/utility.py):

```python
with dai.Pipeline(createImplicitDevice=False) as pipeline:
    for info in device_infos:
        device = pipeline.addDevice(info)
        camera = pipeline.create(dai.node.Camera, device).build(
            dai.CameraBoardSocket.CAM_A
        )
        ...
    pipeline.start()
```

## Demo

![demo_1](https://github.com/user-attachments/assets/6f5e913d-2b25-4f46-b77a-7c0a89821caf)

Just two OAK cameras looking at each other.

Program will also print USB speed, and connected cameras for each connected device before starting the pipeline. Output example for having connected OAK-D S2, OAK-D PRO

```
Found 2 DepthAI devices to configure.
=== Connected to device: 19443010F1E61F1300
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
=== Connected to device: 14442C1011D6C5D600
    >>> Cameras: ['CAM_A', 'CAM_B', 'CAM_C']
    >>> USB speed: SUPER
Pipeline started with 2 device(s).
```

## Usage

Running this example requires at least one (or multiple) **Luxonis device(s)** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d, --devices DEVICES [DEVICES ...]
                      Device IDs or IP addresses to use. If omitted, the devices are discovered.
--include-ip          Also include IP-only cameras (e.g. OAK-4) when discovering devices
--max-devices MAX_DEVICES
                      Limit the number of discovered devices to this count
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
python main.py
```

This will run the demo on the discovered USB devices only; IP devices such as OAK4 are skipped.

```bash
python main.py --include-ip
```

This will also discover and use any TCP/IP cameras on the network.

```bash
python main.py --max-devices 3
```

This will use only the first 3 discovered devices.

```bash
python main.py --include-ip --max-devices 3
```

This will include IP cameras and then only use the first 3 discovered devices.

```bash
python main.py --devices 192.168.1.10 14442C1011D6C5D600
```

This will use exactly the named devices. Prefer this on a network with many cameras.

#### Object detection on multiple devices

Script [multi-device-yolov6.py](multi-device-yolov6.py) will run `YOLOv6 Nano` single shot object detector on all devices and display detections on frames. Each device runs its own `DetectionNetwork` with the model build for its platform.

![demo_2](https://github.com/user-attachments/assets/a700342c-2105-40b0-a831-66efb094b19c)

Run this script with

```bash
python3 multi-device-yolov6.py [--devices ID_OR_IP ...] [--include-ip] [--max-devices N]
```

#### H.264 encoding on multiple devices

The [multi-device-encoding.py](multi-device-encoding.py) script encodes the color camera of every device to H.264 on the device and streams the encoded video to the host, where the Visualizer decodes and displays it.

Run this script with

```bash
python3 multi-device-encoding.py [--devices ID_OR_IP ...] [--include-ip] [--max-devices N]
```
