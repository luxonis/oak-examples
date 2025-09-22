# (OAK 4 Only) Speech Recognition

This example runs [Whisper Tiny EN Network](https://models.luxonis.com/luxonis/whisper-tiny-en/0aaf1b77-761b-44d6-893c-c473ca463186) on an OAK4 device. The example changes the color of the LED on the OAK4 device and adds the same colored tint to the camera output. To record a clip simply press `r` in the stream window and a 5 second audio recording will be made and processed.

**Audio is currently recorded on the host computer.**

> **NOTE:** This example works only on `RVC4` devices.

## Demo

![demo](assets/demo.gif)

## Pipeline description

There are seven nodes comprising the audio processing pipeline:

1. **Audio Encoder:** This node is responsible for recording and processing audio files into a spectrogram.
2. **Whisper Encoder:** This is the Encoder part of the Whisper model that runs on the device. Its input is the spectrogram and it outputs a tensor that needs to be decoded.
3. **Encoder postprocess:** This node adds additional information to the Encoder node that are needed in the Decoder. It sets the recursive decoder values to zero and sets index to 0 as this is the start of the tokens in the audio.
4. **Whisper Decoder:** Computes one iteration of Encoder inputs to get the predicted token. A postprocess node is needed to recursively send outputs back.
5. **Decoder postprocess:** If the Decoder does not predict an End of Text (EOT) Token, this node recursively sends an updated output back to the the decoder to get the next token. Once an EOT Token is predicted, Sends all token so the next node.
6. **Annotation node:** This nodes maps the predicted tokens to text, filters out all words except red, green, blue, yellow, cyan, magenta, white, black, orange, pink, purple and brown. The color of the LED is set to the first detected color. If no color names are detected, no update is performed.
7. **LED set script:** Sets the color of the LED on device.

### Ubuntu prerequisites

If you are using Ubuntu, make sure to install the following packages:

```
    $ sudo apt-get install libportaudio2 libportaudiocpp0 portaudio19-dev
```

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

1. Using pre-recorded audio files with the flag `--audio_file`. This approach sets the color once. We provide some sample audio files in [assets/audio_files](assets/audio_files/). Later color changes can be made with approach two.
2. Recording audio on host machine. By pressing `r` in the viewer, the example will record audio for 5 seconds and use it as the input to the model.

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
--device_ip DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
--audio_file
                    Optional mp4 audio file to use in the example.
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

Running without pre-recorded audio:

```bash
python3 main.py --device_ip <device_ip>
```

Using pre-recorded audio:

```bash
python3 main.py --device_ip <device_ip> --audio_file <audio_file>
```

## Standalone Mode

Standalone mode runs the entire example on the device. Currently, only pre-recored audio files are supported and the recording option will crash the device.

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
