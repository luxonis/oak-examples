# CREStereo: Depth Estimation

This example compares depth output of neural stereo matching using [CREStereo](https://models.luxonis.com/luxonis/crestereo/4729a8bd-54df-467a-92ca-a8a5e70b52ab) to output of stereo disparity. The example works on both RVC2 and RVC4.

There are 2 available model variants for the [CREStereo](https://models.luxonis.com/luxonis/crestereo/4729a8bd-54df-467a-92ca-a8a5e70b52ab) model for each platform. If you choose to use a different model please adjust `fps_limit` argument accordingly.

## Demo

[![CREStereo](media/person.gif)](media/person.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-m MODEL, --model MODEL
                      HubAI model reference of the crestereo model to be used for inference. (default: luxonis/crestereo:iter2-320x240 for RVC2 and luxonis/crestereo:iter4-640x360 for RVC4)
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 2 for RVC2 and 5 for RVC4)
```

- `<DEVICE_FILTER_ENV>`: DepthAI environment variable used for filtering the devices. Usable variables are `DEPTHAI_DEVICE_NAME_LIST` and `DEPTHAI_PLATFORM`. For usage examples see the [subsection below](#examples).

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

This will run the CREStereo example with the default model.

```bash
python3 main.py --fps_limit 5
```

This will run the CREStereo example with the default model, but with a `5` FPS limit.

```bash
DEPTHAI_DEVICE_NAME_LIST=192.168.1.2 python3 main.py
```

This will run the CREStereo example only on device with IP address `192.168.1.2`.

```bash
DEPTHAI_PLATFORM=RVC4 python3 main.py
```

This will run the CREStereo example only on device who's platform is `RVC4`.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
