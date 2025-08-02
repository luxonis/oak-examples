# Hand Pose Estimation

This example demonstrates how to build a 2-stage DepthAI pipeline for hand pose estimation. The pipeline consists of [MediaPipe Palm detector](https://models.luxonis.com/luxonis/mediapipe-palm-detection/9531aba9-ef45-4ad3-ae03-808387d61bf3) and [MediaPipe Hand landmarker](https://models.luxonis.com/luxonis/mediapipe-hand-landmarker/42815cca-deab-4860-b4a9-d44ebbe2988a). The example works on both RVC2 and RVC4. For realtime application you will need to use OAK4 cameras.

By default FPS limit for RVC2 is 6FPS and for RVC4 is 30FPS. You can change this value by setting the `fps_limit` parameter.

After the pose estimation we also apply some logic to recognize the hand gestures. The gestures are: FIST, OK, PEACE, ONE, TWO, THREE, FOUR, and FIVE.

## Demo

[![Hand pose estimation](media/hand-pose.gif)](media/hand-pose.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 5 for RVC2 and 30 for RVC4)
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

```bash
python3 main.py --media <PATH_TO_VIDEO>
```

This will run the example with the default device and the video file.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
