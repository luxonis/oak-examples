# Head Posture Detection

This example demonstrates calculating head poses in a video stream. This is achieved by using a two stage inference DepthAI pipeline to first detect faces and then infer the pitch, yaw and roll of each one. The demo uses [YuNet Face detection model](https://models.luxonis.com/luxonis/yunet/5d635f3c-45c0-41d2-8800-7ca3681b1915) for the first stage and to infer the pose it uses [Head posture model](https://models.luxonis.com/luxonis/head-pose-estimation/068ac18a-de71-4a6e-9f0f-42776c0ef980) from the Luxonis Hub.

**How it works?**

1. Color camera produces high-res frames, that are sent to Face detection NN node.
2. The object detections (faces) are processed by CropConfigsCreator node which generates a dai.ImageManipConfig for each detection.
3. ImageManip node uses the generated configs to crop all detections from the original image frame. It also resizes the cropped detections to (60, 60) which is the input size of the Head posture NN.
4. Head posture NN node infers yaw, pitch and roll from the outputs of the ImageManip node.
5. The original frame, detections and the head postures get synced back together with the use of two Gather nodes (first sync detections and postures, then sync all of them at once to the frame)
6. The synced data is then sent to an AnnotationNode to generate text and bounding box.
7. The annotations and frame are then registered to a dai.RemoteConnection() object to display them in a local browser.

## Demo

<!-- ![Head pose estimation](https://user-images.githubusercontent.com/18037362/172148301-45adb7ce-3aab-478f-8cad-0c05f349ce50.gif) -->

![Head pose estimation](media/head_pose.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 30.0 for RVC4, 6.0 for RVC2)
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

This will run the example with default arguments.

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
