# Point-to-Point Distance Measurement

This application provides real-time 3D distance measurement between two points using DepthAI.
The backend processes video and depth streams to calculate precise 3D Euclidean distances, while the frontend provides an intuitive interface for point selection and measurement display.

The frontend, built using the @luxonis/depthai-viewer-common package, provides real-time video streams with interactive point selection. The backend uses DepthAI's depth estimation capabilities to calculate accurate 3D distances between selected points.

> **Note:** This example works only on RVC4 in standalone mode.

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

## Holistic replay

Replay is optional. The packaged app is still live RVC4. A single `ReplayVideo` file would not carry RGB, the stereo pair, and calibration together.

From this directory, on a computer attached to the RVC4, record and replay the backend with the same arguments. The archive must contain `CAM_A` and the stereo cameras `Depth` opens (`CAM_B` and `CAM_C` on an OAK-D). A failed setup warns `Replay disabled` or `Could not set up holistic replay`. `Replay enabled` is an info line and stays hidden at the default log level. The frontend is still how you click the two points. Replay repeats the frames so the same clicks measure the same scene.

```bash
mkdir -p recordings
DEPTHAI_RECORD="$PWD/recordings" python3 backend/src/main.py
DEPTHAI_REPLAY="$PWD/recordings/recording_<time>.tar.gz" python3 backend/src/main.py
```

Stop the recording with `q` from the visualizer connection, or stop the process. Do not set `DEPTHAI_RECORD` and `DEPTHAI_REPLAY` together. `camera_info.json` replaces the device calibration for that run. Camera replay on RVC4 runs on the device. `oakctl app run` does not see these host environment variables.

The default recording is H.264, so a replayed distance can differ slightly from the live run. Sequence numbers and device timestamps on the first pass are the recorded ones.

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
