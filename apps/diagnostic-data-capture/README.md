# Diagnostic data capture

Preview connected RVC4 cameras in DepthAI Visualizer and save short captures directly to the host. RGB, left, right and ToF sensors are optional. The app detects each connected camera; no StereoDepth node is created. ToF saves processed MID_RANGE depth and confidence, not raw superframes.

## Run

Use Python 3.10+ and install `requirements.txt` in your environment. Connect an idle RVC4 device, then run:

```sh
python main.py --device 10.11.0.33 --output /path/to/captures
```

Open **http://127.0.0.1:8083** (or `localhost`, including through an SSH port forward). After at least five seconds of live sensor warmup, choose the output directory and frame count and click **Start capture**. The default is five frame sets. The page shows completion and the absolute saved path. Streams remain live during and after capture. Press Ctrl+C in the terminal to exit. The output path is on the computer running Python.

With exactly one discoverable camera, `--device` can be omitted. Use `--expected-id SERIAL` to reject an unexpected device at an IP. Check camera occupancy before connecting; the example does not stop other applications.

```sh
python main.py --device CAMERA_IP --frames 5 --warmup 5 --auto-capture --no-gui --output ./captures
```

This bounded mode saves one capture and exits, returning a nonzero code on failure. Other controls: `--fps` (10), `--width` (1280 maximum, full sensor aspect ratio), `--capture-timeout` (60 seconds), `--port` (8083), `--visualizer-port` (8082), `--websocket-port` (8765). All three ports must differ. GUI controls bind to loopback; the SDK Visualizer uses its own network listener. Use on a trusted host/network.

## Capture format

Each capture gets a unique directory containing:

```text
OAK-..._<serial>_<date>/
  calib.json
  metadata.json
  preview.jpg
  left/left_<timestamp>.dai
  right/right_<timestamp>.dai
  rgb/rgb_<timestamp>.dai
  tof_depth/tof_depth_<timestamp>.dai
  tof_confidence/tof_confidence_<timestamp>.dai
```

Only detected streams are present. `preview.jpg` shows the first saved frame set and appears below the saved path in the GUI. It is a thumbnail contact sheet; DAI files retain the original pixel data. Files use native `ImgFrame.save()` serialization, preserving pixel type, geometry, timestamps and exposure metadata. Read with `frame = dai.ImgFrame(); frame.load(path)`. `calib.json` is the original EEPROM calibration. Stereo images are grayscale, unrectified, full-FOV images; RGB is NV12. Preview-only copies label grayscale as RAW8 for compatibility with the bundled Visualizer; saved messages retain their original GRAY8 type. The standard ToF optical grid (including SDK default distortion correction) is recorded and is not aligned to a camera. No stereo depth, disparity, rectified images or ToF raw data are captured.

A host-side DepthAI `Sync` node groups frames by device timestamps within half a frame interval, so only complete matched sets are saved. This groups frames in software; it does not synchronize exposures in hardware. Actual timestamps, sequence IDs, sizes and group skew are recorded. Shared numeric filename keys allow existing capture/replay tools to pair left and right. Slow transport can skip frames; this diagnostic app promises the requested number of matched sets, not uninterrupted video. Warmup starts after every stream has delivered its first frame.

`metadata.json` records device name/ID, OS, SDK, sensors, settings, file paths, duration and completion state. A capture is valid only when `status` is `complete` and all requested sets are present. Partial/error captures remain available for diagnostics and are explicitly labelled.

## Replay

For a capture containing left and right, the `cv-methods` repository accepts the original calibration and nested DAI files directly:

```sh
python generate.py --method neural --model large --device-ip IDLE_RVC4_IP \
  --capture /path/to/capture --timestamp TIMESTAMP --output-dir /path/to/replay
```

Use a numeric timestamp from metadata. RGB-only captures have no stereo replay. Neural depth is a qualitative diagnostic, not a ground-truth accuracy measurement.
