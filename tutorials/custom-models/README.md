# Custom models

This example demonstrates, how to create custom models with PyTorch/Kornia, convert them and run them with DepthAI. For more information see [Conversion](https://rvc4.docs.luxonis.com/software/ai-inference/conversion/) section in the documentation and [README.md](generate_model/README.md) file in the `generate_model/` folder.

`blur.py`, `concat.py`, `diff.py`, `edge.py` and `main.py` are scripts that run created custom models. `generate_model/` folder contains scripts that create these custom models (frame blurring, frame concatenation, frame difference and edge detection).

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
```

### Generating the models

To generate the models, you need to install packages specified in `generate_model/requirements.txt` file:

```bash
pip install -r generate_model/requirements.txt
```

For more information see [README.md](generate_model/README.md) file in the `generate_model/` folder.

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

This will run all models at once on your camera input.

```bash
python3 blur.py
```

This will run the blurring model on your camera input.

```bash
python3 concat.py -fps 10
```

This will run the concatenation model on your camera input with FPS set to 10.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
