# Point-to-Point Distance Measurement

This application provides real-time 3D distance measurement between two points using DepthAI.
The backend processes video and depth streams to calculate precise 3D Euclidean distances, while the frontend provides an intuitive interface for point selection and measurement display.

The frontend, built using the @luxonis/depthai-viewer-common package, provides real-time video streams with interactive point selection. The backend uses DepthAI's depth estimation capabilities to calculate accurate 3D distances between selected points.

> **Note:** Peripheral mode supports RVC2 and RVC4; standalone mode requires RVC4.

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

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

## Peripheral Mode (RVC2 or RVC4)

Requires Python 3.10+ and Node.js 22+.

From this example directory:

```bash
python3 -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ..
python3 backend/src/main.py
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
