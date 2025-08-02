# Human Re-Identification

This example demonstrates how to build a 2-stage DepthAI pipeline for human pose / human face reidentification.
The pipeline consists of a detection model (
[SCRFD Person Detection](https://models.luxonis.com/luxonis/scrfd-person-detection/c3830468-3178-4de6-bc09-0543bbe28b1c),
[SCRFD Face Detection](https://models.luxonis.com/luxonis/scrfd-face-detection/1f3d7546-66e4-43a8-8724-2fa27df1096f), or
[YuNet Face Detection](https://models.luxonis.com/luxonis/yunet/5d635f3c-45c0-41d2-8800-7ca3681b1915)
) predicting bounding boxes around the relevant objects, and a recognition model (
[OSNet](https://models.luxonis.com/luxonis/osnet/6d853621-818b-4fa4-bd9a-d9bdcb5616e6) or
[ArcFace](https://models.luxonis.com/luxonis/arcface/e24a577e-e2ff-4e4f-96b7-4afb63155eac)
) providing embeddings for each of the detected objects.
Object reidentification is achieved by calculating cosine similarity between the embeddings.

## Demo

[![human pose reidentification](media/human_pose_reidentification.gif)](media/human_pose_reidentification.gif)

<sup>[Source](https://www.pexels.com/video/happy-people-walking-on-green-grass-7551577/)</sup>

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 2 for RVC2 and 10 for RVC4)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
-id IDENTIFY, --identify IDENTIFY
                    Determines what object to use for identification ('pose' or 'face'). (default: 'pose')
-cos COS_SIMILARITY_THRESHOLD, --cos_similarity_threshold COS_SIMILARITY_THRESHOLD
                    Cosine similarity between object embeddings above which detections are considered as belonging to the same object. (default: 0.5)
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
