# Data Collection

This application combines on-device open-vocabulary detection with an interactive frontend to **auto-collect “snaps” (images + metadata) under configurable conditions**.\
It runs **YOLOE** on the DepthAI backend, and exposes controls in the UI for:

- Selecting labels (by **text** or **image prompt**)
- Adjusting **confidence threshold**
- Enabling **snap conditions** (timed, no detections, low confidence, lost-in-middle)

> **Note:** RVC4 peripheral or standalone mode. Requires Luxonis OS 1.40 or newer.

![](media/data_collection_app_demo.gif)

## Architecture

### High-level

![](media/high-level-diagram.png)

### In-depth

![](media/in-depth-diagram.png)

## Features

- **Class control**
  - Update classes by text or upload an image to create a visual prompt
- **Confidence filter**
  - Drop detections below a chosen threshold
- **Snapping (auto-capture)**
  - **Timed** (periodic)
  - **No detections** (when a frame has zero detections)
  - **Low confidence** (if any detection falls below threshold)
  - **Lost-in-middle** (object disappears inside central area; edge buffer configurable)
  - Cooldowns **reset** when snapping is (re)started

______________________________________________________________________

## Usage

Running this example requires a **Luxonis RVC4 device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to set up your device if you haven't already.

______________________________________________________________________

## Peripheral Mode (RVC4)

Requires Python 3.12 and Node.js 22+.

From this example directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ..
python backend/src/main.py --device <DEVICE_IP>
```

Open http://localhost:8082 on the host computer. Python runs the backend
and serves `frontend/dist` automatically; streams and controls use port 8765.
Rebuild with `npm run build` in `frontend/` after frontend changes.

## Standalone Mode (RVC4)

In standalone mode, the app runs entirely on the device, with oakapp serving the frontend automatically. To get started, install [oakctl](https://docs.luxonis.com/software-v3/oak-apps/oakctl), then run:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail
