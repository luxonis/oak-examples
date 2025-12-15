# Barcode Detection on Conveyor Belt

This example demonstrates how to detect and decode barcodes in real-time using computer vision. The application is designed for conveyor belt applications where barcodes need to be detected and decoded from video streams. It uses a [barcode detection model](https://models.luxonis.com/luxonis/barcode-detection/75edea0f-79c9-4091-a48c-f81424b3ccab) for detecting barcode regions and combines multiple decoding strategies (pyzbar and zxing-cpp) to ensure robust barcode recognition across various formats and conditions.

The system processes high-resolution camera input, intelligently crops detected barcode regions, and applies multiple fallback decoding strategies including rotation and color inversion to maximize recognition success rates.

## ⚠️ Important Notice

**This application will work poorly on fixed focus devices.** The barcode detection and decoding algorithms require clear, focused images to function effectively. Fixed focus cameras may struggle to capture sharp barcode images at varying distances, leading to:

- Reduced detection accuracy
- Failed barcode decoding attempts
- Inconsistent performance

For optimal results, use devices with autofocus capabilities or ensure barcodes are positioned at the camera's fixed focal distance.

## Recommended Devices

We recommend using **OAK4-CS** for this example. Its **global-shutter** color sensor is best for fast-moving conveyor belts, reducing motion blur and rolling-shutter artifacts that can cause missed or incorrect decodes.

The application will also run on **OAK4-S** and **OAK4-D** devices. For rolling-shutter or fixed-focus variants, keep barcodes near the best-focus distance and ensure good lighting to maximize decoding reliability. See the notice above regarding fixed-focus cameras.

## Demo

![Demo](media/conveyor_application.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 10 for RVC2, 30 for RVC4)
--media_path MEDIA_PATH
                      Optional path to video file for processing instead of live camera feed. (default: None)
```

## Peripheral Mode

### Installation

Install libraries:

**Ubuntu:**

```bash
sudo apt-get update && apt-get install -y libzbar0 libzbar-dev
```

**macOS:**

```bash
brew install zbar
```

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

Start the demo:

```bash
python3 main.py
```

This will run the example with default arguments.

```bash
python3 main.py --device 192.168.1.100 --fps_limit 15
```

This will connect to a specific device and set the FPS limit to 15.

```bash
python3 main.py --media_path test_video.mp4
```

This will process a video file instead of live camera feed.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
