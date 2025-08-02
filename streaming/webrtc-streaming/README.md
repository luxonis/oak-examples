# WebRTC Streaming

This example demonstrates how to setup a WebRTC server to configure the device and stream the results and preview from it.

## Demo

![example](media/example.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

[Enable insecure origins to be treated as secure (Chrome)](https://stackoverflow.com/a/58449078/5494277)

> To ignore Chrome’s secure origin policy, follow these steps. Navigate to chrome://flags/#unsafely-treat-insecure-origin-as-secure in Chrome.\
> Find and enable the Insecure origins treated as secure section (see below). Add any addresses you want to ignore the secure origin policy for. Remember to include the port number too (if required).
> ![example](https://i.stack.imgur.com/8HpYF.png)
> Save and restart Chrome.
> Remember this is for dev purposes only. The live working app will need to be hosted on https.

Build the frontend web application. Go to the `webrtc-streaming/client` folder and run:

```bash
npm install
npm run build
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This will run the WebRTC Streaming example.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
