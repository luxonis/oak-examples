# Box Measurement

This app measures box dimensions (L × W × H) and volume live on an RVC4 device. The boxes have to rest on a flat support plane, for example a conveyor belt. Every box that passes the camera is detected, tracked and measured, and its dimensions are drawn over the color stream. Nothing is saved to the device.

> **Note:** This app requires an **OAK 4 D** device (Pro or non-Pro) - box dimensions are computed from a stereo camera pair. Single-camera devices such as the **OAK 4 S** are not supported. The IR dot projector on Pro models is optional and is enabled automatically when present.

## 1. Install the prerequisites

### oakctl

The app runs entirely on device in standalone mode, as an OAK App. For this you need to install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

If it is already installed, make sure it is the latest version:

```bash
oakctl self-update
oakctl version
```

### Find your device

Make sure your device is connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

All connected devices can be seen with:

```bash
oakctl device list
```

You should see your device with its serial number and IP. You can connect to the device with:

```bash
oakctl connect <DEVICE_IP>
```

## 2. Update LuxonisOS

Make sure your device is on the latest LuxonisOS. Once connected to the device,
check what is available and then apply the update:

```bash
oakctl device update --info
oakctl device update
```

> **Note:** The device needs internet access for OTA update. See [oakctl documentation](https://docs.luxonis.com/software-v3/oak-apps/oakctl#oakctl%20tool-Usage-Device%20Management) for offline updates.

The update takes several minutes and reboots the device. Do not power it off while it runs.

## 3. Run the app

Once you are connected to an RVC4 device, navigate to this directory (`apps/box-measurement`)
and run the following command:

```bash
oakctl app run .
```

The first run builds the container on the device and takes a while. The build installs the box-measurement nodes from [depthai-nodes](https://github.com/luxonis/depthai-nodes) on GitHub (see [backend/requirements.txt](backend/requirements.txt)), so the device needs internet access. Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

## 4. Calibrate the support plane

Nothing is measured until the support plane is confirmed. The app does not remember
the support plane, so you confirm it after every app start. The app UI opens on the
calibration view until you do.

1. **Clear the belt / support plane.** Remove boxes and other objects; the plane must be visible.
2. Open the app UI. The detected candidate plane is highlighted in orange in the
   **Support plane preview**, with the camera distance and tilt next to it.
3. If the highlighted plane is not the one boxes will rest on, press **Next candidate**
   to go through the other detected planes.
4. Press **Confirm support plane**. The UI switches to the measurement view.

If no plane is found, press **Restart calibration**. Recalibrate whenever the camera
is moved or re-aimed, or the belt height changes: press **Recalibrate** in the
measurement view to go back to the calibration view.

## Using the app

The measurement view shows the color stream with each detected box outlined and its
L × W × H (cm) and volume (cm³) overlaid. Its toolbar has:

- **Distance correction** - see below.
- **Detection settings** - the detection confidence threshold (0 to 1). It applies
  immediately and resets to the default when the app restarts.
- **Recalibrate** - discards the confirmed support plane and returns to calibration.

### Distance correction (optional)

If measured heights are consistently too high or too low, correct the distance
to the support plane:

1. Measure the real distance from the camera to the support plane.
2. In the measurement view, open **Distance correction**. It shows the detected distance.
3. Enter the offset as *measured distance − detected distance* (−10 to +10 cm)
   and press **Apply**.

Positive values move the support plane farther from the camera, so boxes measure
taller. The offset mainly affects the height and applies to live measurements right
away. It is cleared when you recalibrate or restart the app.
