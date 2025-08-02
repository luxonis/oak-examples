# YOLOv6 Nano decoding on host

This example shows how to run [YOLOv6 Nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) object detection on DepthAI with decoding on host. The neural network processes the video stream on-device and sends the raw outputs to the host for decoding. The decoding of YOLO's outputs is done in the host node where final bounding boxes in form of a `ImgDetections` message are created.

Alternatively, you can use fully on-device decoding with `DetectionNetwork`.

You can find the tutorial for training the custom YOLO model and generation of *.blob* file [here](https://github.com/luxonis/depthai-ml-training/tree/main/training/others/object-detection) - **YoloV6_training.ipynb** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/luxonis/depthai-ml-training/blob/main/training/others/object-detection/YoloV6_training.ipynb). You can create a copy of the Colab Notebook and try training the model on your own!

## Demo

![Demo](../../generic-example/media/yolov6-nano.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 10 for RVC2 and 30 for RVC4)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
-conf CONFIDENCE_THRESH, --confidence_thresh CONFIDENCE_THRESH
                    set the confidence threshold (default: 0.5)
-iou IOU_THRESH, --iou_thresh IOU_THRESH
                    set the NMS IoU threshold (default: 0.45)
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

This will run the YOLO object detection example with the default device and camera input.

```bash
python3 main.py --media <PATH_TO_VIDEO>
```

This will run the YOLO object detection example with the default device and the video file.

```bash
python3 main.py --device <DEVICE IP OR MXID>
```

This will run the YOLO object detection example with the specified device.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
