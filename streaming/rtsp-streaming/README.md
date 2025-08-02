# RTSP Streaming

This example demonstrates how to stream frames via RTSP server using H265 stream.

## Demo

![rtsp_stream](media/rtsp_stream.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 30)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

#### Ubuntu 20.04

```
sudo apt-get install ffmpeg gstreamer-1.0 gir1.2-gst-rtsp-server-1.0 libgirepository1.0-dev gstreamer1.0-plugins-bad gstreamer1.0-plugins-good gstreamer1.0-plugins-base
python3 -m pip install -r requirements.txt
```

#### Mac OS 11 (Big Sur)

```
brew install pkg-config cairo gobject-introspection gst-plugins-bad gst-plugins-base gstreamer gst-rtsp-server ffmpeg gst-plugins-good
python3 -m pip install -r requirements.txt
```

(if you're using Mac ARM processor, you might have to configure your homebrew properly to install these packages - check [this StackOverflow question](https://stackoverflow.com/q/64882584))

#### Windows

We'd suggest using WSL2 and installing Ubuntu on there. You can use the command apt-get command from Ubuntu above to install necessary dependencies.

### Examples

```bash
python3 main.py
```

This will run the RTSP Streaming example with the default device and camera input.
To see the streamed frames, use a RTSP Client (e.g. VLC Network Stream) with the following link

```
rtsp://localhost:8554/preview
```

On Ubuntu or Mac OS, you can use `ffplay` (part of `ffmpeg` library) to preview the stream

```
ffplay -fflags nobuffer -fflags discardcorrupt -flags low_delay -framedrop rtsp://localhost:8554/preview
```

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
