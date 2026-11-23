# Record Start Stop

This example records H.264 clips from the camera and shows the live preview in the DepthAI Visualizer. A red `REC` mark means a `RecordVideo` segment is open. A gray `IDLE` mark means the node is waiting.

Press `r` or space in the Visualizer to start or stop. Press `q` to quit. The node stays idle until the first start. It keeps a pre-trigger buffer, 60 frames by default, and writes those frames at the start of the next clip.

Each start can carry three limits: a maximum frame count, a maximum duration in milliseconds, and a maximum payload size in 1024-byte units. Reaching a limit closes that segment. The node then waits for the next start. The next file is `frames_s1.mp4`, then `frames_s2.mp4`, and so on.

By default a `DetectionNetwork` looks for people with YOLOv6, and a script node starts a clip when a person is detected. The script stops the clip after 2 seconds with no person, or the record node stops it when a limit is reached. `--target face` uses YuNet instead. `--no-auto-record` still draws detections and records only when you press `r`.

On RVC4 the script sends `RecordControl` itself. On RVC2 the device script cannot construct that type, so the script sends a one-byte command and a host node turns it into `RecordControl`. The preview, the key, and the limits behave the same on both.

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                    Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    Camera, detector, and recorded file frame rate. (default: None)
-o OUTPUT_DIR, --output-dir OUTPUT_DIR
                    Directory that receives the recording when the pipeline stops. (default: recordings)
--pretrigger-frames PRETRIGGER_FRAMES
                    Newest idle frames written at the next start. 0 keeps none. (default: 60)
--max-frames MAX_FRAMES
                    Maximum frames in one segment, including pre-trigger frames. -1 disables the limit. (default: -1)
--max-duration-ms MAX_DURATION_MS
                    Maximum segment length in milliseconds, measured from the moment start is applied. -1 disables the limit. (default: -1)
--max-size-kb MAX_SIZE_KB
                    Maximum written frame payload in 1024-byte units. The frame that reaches the limit is kept. Container bytes are not counted. -1 disables the limit. (default: -1)
--target {person,face}
                    Default detector and label. person uses YOLOv6 COCO. face uses YuNet. (default: person)
-m MODEL, --model MODEL
                    Model Zoo slug, YAML, or descriptor used instead of the --target model. (default: None)
--label LABEL
                    Detection label that arms auto recording. Comma-separated labels are allowed. Defaults to person or face based on --target. (default: None)
--auto-record, --no-auto-record
                    Build the script node that starts a recording on a matching detection and stops it after 2 seconds with no match. --no-auto-record leaves detection on screen and records only from the r key. (default: True)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python >= 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

`requirements.txt` pins `depthai==3.12.1` so it matches the other examples. Released wheels through 3.12.2 do not include `RecordControl` yet. This example needs a depthai build that does, such as the record-replay library.

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This starts the preview, the person detector, and the auto-record script. Clips are written under `recordings/`.

```bash
python3 main.py --no-auto-record --pretrigger-frames 30
```

This records only when you press `r`, and keeps 30 frames from before each start.

```bash
python3 main.py --target face --max-duration-ms 5000 --max-frames 150 --max-size-kb 1024
```

This records a face for at most 5 seconds, 150 frames, or 1024 KiB of frame payload, whichever comes first.

On RVC4 the clip is stored on the device while the pipeline runs and copied into `--output-dir` when the pipeline stops. Quit with `q` so that copy finishes.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
