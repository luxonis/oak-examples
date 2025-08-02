# PoE MQTT publishing

This example demonstrates, how to publish MQTT messages directly from a PoE camera. Credits to [bherbruck](https://github.com/bherbruck) for porting the [paho.mqtt.python](https://github.com/eclipse/paho.mqtt.python) library to a single python file (`paho-mqtt.py`) which can be run inside the [Script node](https://docs.luxonis.com/projects/api/en/latest/components/nodes/script/).

This example publishes a message containing the average number of objects detected in the last 10 seconds. It uses [YOLOv6 Nano](https://models.luxonis.com/luxonis/yolov6-nano/face58c4-45ab-42a0-bafc-19f9fee8a034) model for object detection.

By default, the messages are published to a public broker `test.mosquitto.org` on port `1883`. They are published to the topic `test_topic/detections`. This can be changed with available CLI arguments (see Usage section below).

## Demo

![mqtt-client](media/mqtt_client.gif)

For the demo https://testclient-cloud.mqtt.cool/ was used.

## Usage

Running this example requires a **Luxonis PoE device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit. (default: None)
-media MEDIA_PATH, --media_path MEDIA_PATH
                    Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
-b BROKER, --broker BROKER
                    MQTT broker address. (default: test.mosquitto.org)
-p PORT, --port PORT  MQTT broker port. (default: 1883)
-t TOPIC, --topic TOPIC
                    MQTT topic to publish to. (default: test_topic/detections)
-u USERNAME, --username USERNAME
                    MQTT broker username. (default: )
-pw PASSWORD, --password PASSWORD
                    MQTT broker password. (default: )
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

This will run the example with default argument values and publish messages to `test.mosquitto.org` on port `1883`.

```bash
python3 main.py \
    --broker localhost \
    --port 1883 \
    --topic my_topic/detections \
    --username my_username \
    --password my_password
```

This will publish messages to `localhost` on port `1883`. It will use `my_username` and `my_password` credentials to authenticate to the broker. It will publish messages to the topic `my_topic/detections`.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
