# On Device Encoding

This example demonstrates how to stream encoded frames from the device to the host and save them directly into a video container. **Video is encoded on the device itself** before it's sent to the host computer.

This demo uses codecs that some video players (eg. Quicktime) might not support. We suggest using [VLC](https://www.videolan.org/vlc/) to play the video.

## Demo

![example](media/example.png)

As you can see, the `video.mp4` uses the codec of the stream being saved, so there's no decoding/encoding (or converting) happening on the host computer and **host CPU/GPU/RAM usage is minimal**.

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 30)
-c {h264,h265,mjpeg}, --codec {h264,h265,mjpeg}
                    Video encoding (h264 is default) (default: h264)
-o OUTPUT, --output OUTPUT
                    Path to the output file. (default: video.mp4)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This will run the On Device Encoding example with the default device, camera input and H264 codec.

```bash
python3 main.py --codec h265 --output video_h265.mp4
```

This will run the On Device Encoding example with the default device, H265 codec and `video_h265.mp4` output file.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
