# XFeat: Accelerated Features for Lightweight Image Matching

This example demonstrates how to use the XFeat model from Luxonis HubAI with the DepthAI platform. XFeat has compact descriptors (64D) and simple architecture components that facilitate deployment on embedded devices. Performance is comparable to known deep local features such as SuperPoint while being significantly faster and more lightweight.

The example uses [XFeat](https://models.luxonis.com/luxonis/xfeat/6c2790a1-bf68-4e89-a4b3-5c9ae68183b5) model.

We offer two modes of operation: `mono` and `stereo`. In `mono` mode we use a single camera as an input and match the frames to the reference image. In `stereo` mode we use two cameras to match the frames to each other.
In `mono` mode we visualize the matches between the frames and the reference frame which can be set by pressing `s` key in the visualizer. In `stereo` mode we visualize the matches between the frames from the left and right camera.

> **Note:** If you want to run the example in `stereo` mode, you need a device with at least 2 cameras (left and right).

> **Note:** Some model operations are not supported on-device and will be run on the host computer. This means that the speed of the app will be affected by the host computer's power. We have set some default FPS limits and `maxNumKeypoints` to ensure that the app runs smoothly on most machines. Feel free to increase the FPS limit if you have a powerful enough machine. To increase the maximum matched keypoints change the `setMaxKeypoints` function in the `mono.py` or `stereo.py` file.

## Demo

![XFeat Mono Demo on OAK](media/xfeat_demo.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-m MODEL, --model MODEL
                    The HubAI model reference for XFeat model. Get it from the Luxonis HubAI. (default: luxonis/xfeat:mono-320x240)
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 5 for stereo mode and 10 for mono mode)
```

**NOTE**:

- Stereo mode will run only with 2-camera devices.
- If you use model with mono mode (e.g. `luxonis/xfeat:mono-320x240`), you can set reference frame by pressing `s` key in the visualizer.

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

This will run the XFeat model in mono mode with the default model and device. Default model: `luxonis/xfeat:mono-320x240`.

```bash
python3 main.py --model luxonis/xfeat:mono-640x480
```

This will run the XFeat model in mono mode with the `luxonis/xfeat:mono-640x480` model. This model is more accurate but slower than the default model.

```bash
python3 main.py --model luxonis/xfeat:stereo-320x240
```

This will run the XFeat model in stereo mode with the `luxonis/xfeat:stereo-320x240` model. The model will match the frames from two cameras (e.g. left and right camera).

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
