# Play Encoded Stream

This example shows how you can play H264/H265/MJPEG encoded streams on the host computer. It showcases three different ways of playing the encoded stream.

- `main.py` using Visualizer: This plays encoded stream by passing it directly to Visualizer. This is the most straightforward way of playing the encoded stream, however, it is currently not possible to play H265 encoded streams using Visualizer.

- `pyav.py` using PyAv library: This decodes encoded stream using the PyAv library and then displays them using Visualizer. This supports H264, MJPEG and H265 encoded streams.

- `mjpeg.py` with OpenCV decoding: This decodes encoded stream using OpenCV's [cv2.imdecode()](https://docs.opencv.org/3.4/d4/da8/group__imgcodecs.html#ga26a67788faa58ade337f8d28ba0eb19e) function and displays them using Visualizer. This example supports only MJPEG encoding. Note that MJPEG compression isn't as great compared to H.264/H.265.

## Demo

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect
                    to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 30)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If
                    not set, the model will run on the camera input.
                    (default: None)
-enc {mjpeg,h265,h264}, --encode {mjpeg,h265,h264}
                    Select encoding format. (default: h264)

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

This will run the example with default argument values and will play the encoded stream on the host computer.

```bash
python3 pyav.py -fps 10
```

This will run the the example at 10 FPS and will use PyAv to decode the encoded stream.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
