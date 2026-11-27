# Raw Stream

This example project demonstrates how to use the `@luxonis/depthai-viewer-common` package to build a simple custom frontend application for DepthAIv3. It showcases how to stream data to a custom UI that includes a text input, allowing two-way communication between the frontend and the backend application. In peripheral mode, `depthai_nodes.runtime.serve_frontend` serves the built frontend on the host. In standalone mode, oakapp serves it through its HTTPS proxy. For scenarios involving remote access via WebRTC and support for stream encoding, which requires HTTPS access, it is recommended to use the advanced example [open-vocabulary-object-detection](../open-vocabulary-object-detection/README.md).

## Demo

![Custom Request](media/message_sending.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
					Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps-limit FPS_LIMIT
					FPS limit. (default: None)
-ip IP, --ip IP       IP address to serve the frontend on. (default: 127.0.0.1)
-p PORT, --port PORT  Port to serve the frontend on. (default: 8082)
--frontend-dir PATH  Override the built frontend directory.
--no-frontend        Use a separate frontend server.
```

## Peripheral Mode

Requires Python 3.10+ and Node.js 22+.

Use the USB device ID for RVC2 or the device IP for RVC4 as `<DEVICE>`.

From this example directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python main.py --device <DEVICE>
```

Open http://localhost:8082 on the host computer. Python runs the backend
and serves `frontend/dist` automatically; streams and controls use port 8765.
Rebuild with `npm run build` in `frontend/` after frontend changes.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).

Open the frontend URL reported by `oakctl` (normally `https://<DEVICE_IP>:9000`). The oakapp runtime serves the frontend; the Python HTTP helper stays disabled automatically.
