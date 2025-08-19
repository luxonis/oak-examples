# License Plate Recognition

This example demonstrates how to run 3 stage inference on DepthAI. Its focus is on an automatic license plate recognition (ALPR) task.
First, a vehicle is detected on the image, the cropped image is then fed into a license plate detection model. The cropped license plate is sent to a text recognition (OCR) network, which tries to decode the license plates texts.

It uses 3 models from our ZOO:

- [YOLOv6 nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) for vehicle detection.
- [License Plate Detection](https://models.luxonis.com/luxonis/license-plate-detection/7ded2dab-25b4-4998-9462-cba2fcc6c5ef) for detecting the license plates.
- [PaddlePaddle Rext Recognition](https://models.luxonis.com/luxonis/paddle-text-recognition/9ae12b58-3551-49b1-af22-721ba4bcf269) for recognizing text on license plates.

**NOTE**: Due to the high computational cost, this example only works on OAK4 devices.

Take a look at [How to Train and Deploy a License Plate Detector to the Luxonis OAK](https://blog.roboflow.com/oak-deploy-license-plate/) tutorial for training a custom detector using the Roboflow platform.

## Demo

![Detection Output](media/lpr.gif)

<sup>[Source](https://www.pexels.com/video/speeding-multicolored-cars-trucks-and-suv-motor-vehicles-exit-a-dark-new-york-city-underground-tunnel-which-is-wrapped-in-the-lush-green-embrace-of-trees-and-bushes-17108719/)</sup>

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-media MEDIA_PATH, --media_path MEDIA_PATH
                      Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
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

This will run the example with the default device and camera input.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
