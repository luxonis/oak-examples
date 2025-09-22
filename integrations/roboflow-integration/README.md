# Roboflow Integration

This example shows how to create a [Roboflow](https://roboflow.com) dataset using detections from a **Luxonis device**. It uses [YOLOv6 Nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model for object detection.

## Demo

Link to the [**video**](https://github.com/user-attachments/assets/a07070a8-6267-4348-8342-ddf77c9ddd8b).

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
  -d DEVICE, --device DEVICE
                        Optional name, DeviceID or IP of the camera to connect
                        to. (default: None)
  -fps FPS_LIMIT, --fps_limit FPS_LIMIT
                        FPS limit for the model runtime. (default: None)
  -media MEDIA_PATH, --media_path MEDIA_PATH
                        Path to the media file you aim to run the model on. If
                        not set, the model will run on the camera input. (default: None)
  -key API_KEY, --api-key API_KEY
                        private API key copied from app.roboflow.com (default: None)
  --workspace WORKSPACE
                        Name of the workspace in app.roboflow.com (default: None)
  --dataset DATASET     Project ID in app.roboflow.com (default: None)
  --auto-interval AUTO_INTERVAL
                        Automatically upload annotations every [SECONDS] seconds (default: None)
  --auto-threshold AUTO_THRESHOLD
                        Automatically upload annotations with confidence above
                        [AUTO_THRESHOLD] (when used with --auto-interval) (default: 0.5)
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
python3 main.py --api-key <API_KEY> --workspace <WORKSPACE_NAME> --dataset <DATASET_NAME>
```

This will run the Roboflow Integration example with the default device and camera input. It will upload detections only when `space` key is pressed.

```bash
python3 main.py --api-key <API_KEY> --workspace <WORKSPACE_NAME> --dataset <DATASET_NAME> --auto-interval <SECONDS>
```

This will run the Roboflow Integration example with the default device and camera input. It will automatically upload detections every `<SECONDS>` seconds or when `space` key is pressed.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

Replace `<API_KEY>`, `<WORKSPACE_NAME>` and `<DATASET_NAME>` with your Roboflow API key, workspace and dataset names in the [oakapp.toml](oakapp.toml) file.

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
