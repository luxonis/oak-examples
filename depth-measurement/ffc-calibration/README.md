# FFC Calibration

This example calibrates a multi-camera setup and provides two entrypoints:

- `main.py` - terminal-driven workflow that lets you select a device, enter baselines, run dynamic calibration, inspect stereo pairs, preview depth, and flash the resulting calibration.
- `opencv.py` - interactive OpenCV workflow with a live coordinate-frame plot that keeps updating while calibration is running.
- `visualizer.py` - DepthAI visualizer backend for the custom FFC frontend. The browser UI owns baseline entry, stereo pair buttons, and flashing.

## Notes

- The visualizer workflow keeps a 2x2 stream layout: dashboard/3D camera pose, left stream, right stream, and depth.
- Dynamic calibration progress is rendered directly in the dashboard tile.
- To run against locally built DepthAI Python bindings, set `PYTHONPATH` or `DEPTHAI_PYTHON_BINDINGS` to the bindings directory before starting the script.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python3 main.py --device <DEVICE>
python3 opencv.py --device <DEVICE>
python3 visualizer.py --device <DEVICE>
```

For the custom visualizer frontend during local development, run the backend and frontend separately:

```bash
python3 visualizer.py --device <DEVICE>
cd frontend
npm install
npm run dev
```

Open the Vite URL shown by `npm run dev`. The frontend connects to the DepthAI websocket exposed by `visualizer.py`.
