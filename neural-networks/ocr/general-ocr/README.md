# General OCR

This example runs two-stage text detection and recognition with the existing PaddlePaddle [Text Detection](https://models.luxonis.com/luxonis/paddle-text-detection/131d855c-60b1-4634-a14d-1269bb35dcd2) and [Text Recognition](https://models.luxonis.com/luxonis/paddle-text-recognition/9ae12b58-3551-49b1-af22-721ba4bcf269) models from the Luxonis Model Zoo. It rectifies rotated detections, preserves the aspect ratio of recognition crops with white padding, and draws the recognized text and confidence over the full-resolution source video. The Visualizer exposes `Video` and `Text`.

## Demo

![Detection Output](media/highway-sign-ocr.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: the first locally available device is used)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    Camera/replay FPS limit. (default: 5 on RVC2, 30 on RVC4)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
--detection_confidence FLOAT
                    Minimum confidence for a text crop. (default: 0.5)
--min_crop_width INT, --min_crop_height INT
                    Minimum expanded text-box size in source pixels. (default: 50 x 12)
--recognition_confidence FLOAT
                    Minimum recognition confidence shown in overlays. (default: 0.25)
--min_text_length INT
                    Minimum recognized text length shown in overlays. (default: 1)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

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

For text-dense scenes, a lower `--fps_limit` may help avoid a recognition backlog because every detected region runs through the recognizer.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
