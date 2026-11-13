# Box Measurement

This app measures box dimensions (L × W × H) and volume live on an RVC4 device. The boxes have to rest on a flat support plane, for example a conveyor belt. Every box that passes the camera is detected, tracked and measured, and its dimensions are drawn over the color stream. Nothing is saved to the device.

The backend runs the box-measurement nodes from [depthai-nodes](https://github.com/luxonis/depthai-nodes) on neural stereo depth. The frontend, built on `@luxonis/depthai-viewer-common`, guides you through support plane calibration and then shows the measurements.

> **Note:** This example works only on RVC4 in standalone mode, and requires an **OAK 4 D** (Pro or non-Pro): box dimensions are computed from a stereo camera pair, so single-camera devices such as the **OAK 4 S** are not supported. The IR dot projector on Pro models is enabled automatically when present.

## Features

- **Live box measurement:** instance segmentation, per-box tracking and L × W × H / volume measured against the support plane
- **Support plane calibration:** support plane candidates checked against gravity from the IMU, a live preview of the highlighted candidate, and operator confirmation
- **Distance offset:** a ±10 cm correction for box heights that come out consistently too high or too low
- **Detection settings:** the detection confidence threshold, applied live

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

The first run builds the container on the device and takes a while. The device needs internet access, since the app downloads its segmentation model on first start.

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail page

## Support Plane Calibration

Nothing is measured until the support plane is confirmed. The app does not remember
the support plane, so the app UI opens on the **Support plane calibration** view after
every app start.

1. **Clear the belt / support plane.** Remove boxes and other objects; the plane must be visible.
2. The detected candidate plane is highlighted in orange in the **Support plane preview**,
   with the camera distance and tilt next to it.
3. If the highlighted plane is not the one boxes will rest on, press **Next candidate**
   to go through the other detected planes.
4. Press **Confirm support plane**. The UI switches to the measurement view.

Until a plane is found the view keeps showing **Searching for a support plane…**; the
app keeps looking on its own, so check that the support plane is clear and in view.
Press **Restart calibration** to discard the current candidates and search again,
for example after clearing the belt. Repeat support plane calibration whenever the
camera is moved or re-aimed, or the belt height changes: press **Recalibrate** in the
measurement view.

## Measuring Boxes

The measurement view shows the color stream with each detected box outlined and its
L × W × H (cm) and volume (cm³) overlaid. Its toolbar has:

- **Distance offset** - see below.
- **Detection settings** - the detection confidence threshold (0 to 1). It applies
  immediately and resets to the default when the app restarts.
- **Recalibrate** - discards the confirmed support plane and returns to support plane
  calibration.

### Distance offset (optional)

If measured heights are consistently too high or too low, add a distance offset to
the camera's distance from the support plane:

1. Measure the real distance from the camera to the support plane.
2. In the measurement view, open **Distance offset**. It shows the detected distance.
3. Enter the offset as *measured distance − detected distance* (−10 to +10 cm), using
   the field or the **−** and **+** buttons, and press **Apply**. The panel shows the
   **Distance with offset**. **Clear offset** removes the offset right away.

Positive values move the support plane farther from the camera, so boxes measure
taller. The offset mainly affects the height and applies to live measurements right
away. It is cleared when you run support plane calibration again or restart the app.
