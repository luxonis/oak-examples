# Box Measurement

This app measures box dimensions (L × W × H) and volume on an RVC4 device. The boxes have to be on a flat surface, for example on a conveyor belt. Every box that passes the camera is detected, tracked and measured; the app stores a measurement event with a video clip for each box and keeps a rolling continuous recording of the color stream.

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

The first run builds the container on the device and takes a while. Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

## 4. Calibrate the support plane

Nothing is measured until the support plane is confirmed, so do this first.

1. **Clear the belt / support surface.** The surface must be visible.
2. Open the app UI and go to **Calibration**.
3. The candidate plane is highlighted in orange.
4. If the highlighted surface is not the surface you want to measure on, press **Next surface** to go through the other detected planes.
5. Press **Confirm surface**. The plane turns green and is saved to the device,
   so it survives app and device restarts.

Recalibrate whenever the camera is moved, re-aimed, or the belt
height changes.

### Distance correction (optional)

If measured heights are consistently too high or too low, correct the distance
to the surface:

1. Measure the real distance from the camera to the surface.
2. On the **Calibration** page, open **Distance correction**. It shows the detected distance.
3. Enter the offset as *measured distance − detected distance* (−10 to +10 cm)
   and press **Apply**.

Positive values move the reference surface farther from the camera, so boxes
measure taller. The offset mainly affects the height. It is saved together with the
plane, and it is cleared when you press **Restart calibration**.

## Using the app

The UI has five pages:

- **Home** - the color stream with detections, per-box dimensions and volume
  overlaid.
- **Calibration** - the support-plane flow described above.
- **Events** - one card per measured box, with dimensions, volume, a snapshot
  and a video clip. Events are one of:
  - `SUCCESS` - a stable measurement was reached.
  - `INCOMPLETE` - the box left the frame before the measurement stabilized.
  - `FAILED_LOW_COVERAGE` - no usable measurement was taken, most often
    because too few depth points on the box were valid.
- **Footage** - the rolling continuous recording, split into chunks. Can be played from the UI.
- **Settings**.

The UI shows measurements in cm and volume in cm³.

## Exporting events

On the **Events** page, press **Create archive** to pack all events (dimensions,
images, videos), the settings, the support plane and the app logs into one ZIP on
the device. When it is ready, copy the command shown on the page and run it on your
computer to download the archive.

- Only one archive is kept; a new one replaces the previous one.
- **Delete the archive after downloading it.** It takes about as much space as all
  events, and a large export can cause the oldest continuous recordings to be removed.
- Continuous recordings are not included in the archive.

Archive contents:

- `manifest.json` - app version, pipeline configuration, event count, missing files, log information and warnings.
- `configuration/settings.json` - app settings at export time.
- `configuration/support_plane.json` - confirmed support-plane equation and distance offset, if available.
- `events/events.jsonl` - one JSON record per event, including ID, type, track ID, UTC timestamp, dimensions (mm), volume (mm³) and file paths.
- `events/files/<event id>/` - event images (`.jpg`) and video clips (`.mp4`), when available.
- `logs/` - `application.log` and its rotated backups.