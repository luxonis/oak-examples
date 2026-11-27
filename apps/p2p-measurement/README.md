# Point-to-Point Distance Measurement

This application provides real-time 3D distance measurement between two points using DepthAI.
The backend processes video and depth streams to calculate precise 3D Euclidean distances, while the frontend provides an intuitive interface for point selection and measurement display.

The frontend, built using the @luxonis/depthai-viewer-common package, provides real-time video streams with interactive point selection. The backend uses DepthAI's depth estimation capabilities to calculate accurate 3D distances between selected points.

> **Note:** This example works on RVC4 (standalone and peripheral mode) and RVC2 (peripheral mode).

## Demo

![](media/demo.gif)

## Features

- **Real-time 3D Distance Measurement:** Precise Euclidean distance calculation between two points
- **Interactive Point Selection:** Click-to-select interface with visual feedback
- **Unit Conversion:** Switch between metric (meters) and imperial (feet) units
- **Precision Control:** Adjustable decimal places for distance display
- **Tracking Modes:** Toggle between active tracking and static point display
- **Standard Deviation:** Display measurement uncertainty when available

## Usage

Running this example requires a **Luxonis device** (RVC2 or RVC4) connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

### Available Arguments

```text
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: None)
--no-frontend         Disable serving the static frontend bundle from Python.
--frontend-ip FRONTEND_IP
                      IP address to serve the static frontend bundle on in peripheral mode. (default: 0.0.0.0)
--frontend-port FRONTEND_PORT
                      Port to serve the static frontend bundle on in peripheral mode. (default: 8082)
--frontend-dir FRONTEND_DIR
                      Path to the built static frontend bundle directory. (default: frontend/dist or OAKAPP_STATIC_FRONTEND_PATH)
--https, --use-ssl    Serve the local peripheral frontend over HTTPS using a self-signed or provided TLS certificate.
--certificate-path CERTIFICATE_PATH
                      Path to TLS certificate (.crt) file used when --https is enabled.
--key-path KEY_PATH   Path to TLS private key (.key) file used when --https is enabled.
```

## Peripheral Mode

In peripheral mode, the Python backend runs on your host computer and starts a built-in HTTP/HTTPS server to serve the built static frontend bundle (`frontend/dist`).

### Installation

#### Backend

Install the Python dependencies from the example root:

```bash
pip install -r backend/requirements.txt
```

#### Frontend

Ensure [Node.js](https://nodejs.org/en/download/) (v24 or higher recommended) is installed, then install dependencies and build the static bundle:

```bash
cd frontend
npm ci
npm run build
cd ..
```

### Running in Peripheral Mode

From the `apps/p2p-measurement` directory, run:

```bash
python3 backend/src/main.py
```

Open `http://localhost:8082` in your browser.

To serve the frontend over local HTTPS (generating a self-signed certificate for `localhost` under `.https/` if none is provided):

```bash
python3 backend/src/main.py --https
```

Then open `https://localhost:8082` in your browser (accepting the self-signed certificate prompt on first visit). You can also supply your own certificate with `--certificate-path` and `--key-path`.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device. In this mode, the Python web server is excluded (`--no-frontend` in `oakapp.toml` and `OAKAPP_STATIC_FRONTEND_PORT` detection) and the static frontend bundle is built and served directly by the oakapp runtime.
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
2. And then you can just remotly open App UI via App detail

### How to Use

1. **Select Points:** Click on the video stream to select two points
2. **View Distance:** The 3D Euclidean distance will be displayed in real-time
3. **Clear Points:** Press **Space** or right-click to reset
4. **Toggle Tracking:** Use the tracking button to enable/disable point tracking
5. **Change Units:** Switch between metric (m) and imperial (ft) units
6. **Adjust Precision:** Select decimal places for distance display
