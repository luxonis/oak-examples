# Cumulative Object Counting

This example demonstrates how to run an inference pipeline for cummulative object counting using the DepthAI and OAK cameras.
It utilizes an object detection model to detect objects (e.g. `people`) and counts how many pass in an upward and downward direction.
By default it uses [YOLOv6 Nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model but you can also try running it with some other general object detection model as, for example, [Mobilenet-SSD](https://models.luxonis.com/luxonis/mobilenet-ssd/2da6e0a5-4785-488d-8cf5-c35f7ec1a1ed).

The example is inspired by / based on:

- [Tensorflow 2 Object Counting](https://github.com/TannerGilbert/Tensorflow-2-Object-Counting)
- [OpenCV People Counter](https://www.pyimagesearch.com/2018/08/13/opencv-people-counter/)
- [tensorflow_object_counting_api](https://github.com/ahmetozlu/tensorflow_object_counting_api)

## Demo

![cumulative object counting](media/cumulative-object-counting.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-m MODEL, --model MODEL
                      HubAI reference of the object detection model. (default: luxonis/yolov6-nano:r2-coco-512x288)
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 25)
-media MEDIA_PATH, --media_path MEDIA_PATH
                      Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
-a AXIS, --axis AXIS
                      Axis for cumulative counting (either x or y). (default: x)
-roi ROI_POSITION, --roi_position ROI_POSITION
                      osition of the axis (if 0.5, axis is placed in the middle of the frame). (default: 0.5)
```

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

This will run the example with default arguments.

```bash
python3 main.py -d <DEVICE_IP>
```

This will run the cumulative object counting example with the provided device ip, camera input and default fps limit based on the device.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
