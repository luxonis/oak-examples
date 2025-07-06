# Dynamic YOLO World

This example demonstrates an advanced use of a custom frontend. On the DepthAI backend, it runs the YOLO-World model on-device, with configurable class labels and confidence threshold — both controllable via the frontend.
The frontend, built using the `@luxonis/depthai-viewer-common` package, displays a real-time video stream with detections. It is combined with the [default oakapp docker image](https://hub.docker.com/r/luxonis/oakapp-base), which enables remote access via WebRTC.

> **Note:** This example works only on RVC4 in standalone mode.

## Demo

![dynamic-yolo-world](media/dynamic_yolo_world.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
					Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps-limit FPS_LIMIT
					FPS limit. (default: None)
-ip IP, --ip IP       IP address to serve the frontend on. (default: None)
-p PORT, --port PORT  Port to serve the frontend on. (default: None)
```

Before running the example you’ll need to first build the frontend. Follow these steps:

1. Install FE dependencies: `cd frontend/ && npm i`
1. Build the FE: `npm run build`
1. Move back to origin directory: `cd ..`

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
1. And then you can just remotly open App UI via App detail
