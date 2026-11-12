# Diagnostic data capture

Preview connected RVC4 cameras in DepthAI Visualizer and save short captures on the host or directly on an RVC4 device. RGB, left, right and ToF sensors are optional. The app detects each connected camera; no StereoDepth node is created. ToF saves processed MID_RANGE depth and confidence, not raw superframes.

## Run on the host

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

## Run on the device (standalone)

Check that the RVC4 device is idle, then build and run the app with oakctl:

```sh
oakctl app run . -d CAMERA_IP
```

On older devices, choose a compatible SDK at build time. The ToF device running Luxonis OS 1.38.1 was tested with DepthAI 3.11.0; 3.12.1 failed to open its local device connection:

```sh
oakctl app run . -d CAMERA_IP --build-arg DEPTHAI_VERSION=3.11.0
```

Open the **HTTPS frontend URL shown by oakctl** using the device's IP address. Accept the device's self-signed certificate if your browser prompts. The capture controls, embedded Visualizer, and downloads share this URL. Direct IP access on a trusted network is supported; Hub/WebRTC access to the capture HTTP controls is not supported.

In this mode, Python runs on the OAK. Captures default to `$OAKAGENT_STORAGE_APP/captures`, persistent app storage supplied by oak-agent. The GUI labels this **Save to device folder**, and permits subfolders within that capture directory. Captures survive app stops and restarts; removing the app or its storage can remove them. Host paths on your computer are not accessible from this mode.

After a capture completes, click **Download capture (.zip)** to save it to your computer. The ZIP includes the original DAI files, calibration, metadata, and preview. Downloads stream directly without creating another recording-sized file on the device. The button downloads the latest completed capture in the current app session; starting a new capture clears the button until that capture finishes. Older captures remain in the persistent directory and can be retrieved with device storage tools. Downloading does not delete the device copy.

Stop the development app with Ctrl+C in the attached oakctl session, or:

```sh
oakctl app stop 000 -d CAMERA_IP
```

`oakapp.toml` supplies `--standalone` automatically. RVC2 is not supported in either mode. In host mode the same download button is available, and captures still save directly to your computer.

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

A CPU-side DepthAI `Sync` node groups frames by device timestamps within half a frame interval, so only complete matched sets are saved. The CPU is on your computer in host mode and on the OAK in standalone mode. This groups frames in software; it does not synchronize exposures in hardware. Actual timestamps, sequence IDs, sizes and group skew are recorded. Shared numeric filename keys allow existing capture/replay tools to pair left and right. Slow transport can skip frames; this diagnostic app promises the requested number of matched sets, not uninterrupted video. Warmup starts after every stream has delivered its first frame.

`metadata.json` records device name/ID, OS, SDK, sensors, settings, file paths, duration and completion state. A capture is valid only when `status` is `complete` and all requested sets are present. Partial/error captures remain available for diagnostics and are explicitly labelled.

## Replay

For a capture containing left and right, the `cv-methods` repository accepts the original calibration and nested DAI files directly:

```sh
python generate.py --method neural --model large --device-ip IDLE_RVC4_IP \
  --capture /path/to/capture --timestamp TIMESTAMP --output-dir /path/to/replay
```

Use a numeric timestamp from metadata. RGB-only captures have no stereo replay. Neural depth is a qualitative diagnostic, not a ground-truth accuracy measurement.
