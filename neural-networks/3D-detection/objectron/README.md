# Objectron: 3D Bounding Box Detection

This example demonstrates how to perform 3D object detection using the [Objectron](https://models.luxonis.com/luxonis/objectron/4c7a51db-9cbe-4aee-a4c1-b8abbbe18c11) model. The model can predict 3D bounding box of the foreground object in the image. For general object detection we use [YOLOv6](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model. The pipepile is a standard 2-stage pipeline with detection and 3D object detection models. The example works on both RVC2 and RVC4. [Objectron](https://models.luxonis.com/luxonis/objectron/4c7a51db-9cbe-4aee-a4c1-b8abbbe18c11) can predict 3D bounding boxes for chairs, cameras, cups, and shoes.

## Demo

[![objectron](media/chair.gif)](media/chair.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 5 for RVC2, 15 for RVC4)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
```

**NOTE**: The provided example detects chairs, but you can change the object class by changing the `VALID_LABELS` constant in `main.py` (e.g. `VALID_LABELS=[41])` where `41` is the label for cups).
Camera and shoes can not be detected with general YOLOv6 detector. So, you need to provide your own detector for these objects.

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This will run the objectron example with default connected device, camera input and default fps limit based on the device.

```bash
python3 main.py -d <DEVICE_IP>
```

This will run the objectron example with the provided device ip, camera input and default fps limit based on the device.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
