# Barcode Detection on Conveyor Belt – Controller Box Strobe Example

This example demonstrates **real-time barcode detection and decoding** on a conveyor belt using DepthAI cameras. It uses a combination of **pyzbar** and multi-frame validation to ensure robust detection. Additionally, this version includes **temporal smoothing** of bounding boxes to reduce jitter and improve visual tracking.

> **Note:** This example works only on OAK4 in standalone mode. It is not supported in host-driven peripheral mode because the M8 Controller Box is connected directly to the OAK4 device.

## Functionality

* Detects and decodes barcodes from live camera feed.
* Draws **bounding boxes** around detected barcodes, with temporal smoothing over 2–3 frames.
* Highlights **valid barcodes** in green, other detections in red.
* Stops and restarts a conveyor using a simple **state machine** when barcodes are detected.
* Streams live video over HTTP MJPEG for visualization.

## Recommended Devices

* **OAK4-CS** – Best for fast-moving conveyor belts, global-shutter color sensor minimizes motion blur.
* **OAK4-S / OAK4-D** – Works with good lighting; best to keep barcodes near optimal focus distance.

> Fixed-focus cameras may result in inconsistent detection and decoding performance.

## Demo

![Demo](media/conveyor_application.gif)

### Standalone Mode (RVC4 only)

This app is designed to run entirely on the device.

1. Install `oakctl` by following the instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).
2. From this directory, connect to the device and run the app:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

### Peripheral Mode (Host + Device)

This mode is not supported for this example. The M8 Controller Box must be attached directly to the OAK4 device running the app.

### Configuration

* `TEMPORAL_SMOOTHING` – Toggle smoothing of bounding boxes.
* `SMOOTHING_ALPHA` – Adjust smoothing weight.
* `STOP_DURATION` – Duration to stop conveyor on barcode detection.
* `COOLDOWN_TIME` – Time before a scanned barcode expires.
