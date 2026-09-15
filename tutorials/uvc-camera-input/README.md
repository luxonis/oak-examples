# UVC Camera Input

This example captures frames from a USB UVC camera with OpenCV, wraps them as DepthAI `ImgFrame` messages, and feeds them into a DepthAI pipeline. The included pipeline sends the frames through an `ImageManip` node before publishing them to the DepthAI Visualizer.

Use this when you want to prototype a non-onboard camera as an image source for DepthAI nodes such as `ImageManip`, `NeuralNetwork`, or `DetectionNetwork`.

## Usage

Running this example requires a **Luxonis device** and a USB UVC camera visible to the host running the Python process.

- In peripheral mode, the UVC camera must be attached to the host computer.
- In standalone mode on RVC4, the UVC camera must be attached to the OAK device and visible as `/dev/video*`.

The default source is `auto`, which searches Linux USB video nodes and uses the first one that produces frames. On Windows it falls back to OpenCV camera index `0`.

Available parameters:

```text
-d DEVICE, --device DEVICE
                    Optional name, DeviceID, or IP of the DepthAI device to connect to.
--uvc-device UVC_DEVICE
                    UVC source to open. Use 'auto', a Linux path like /dev/video2, or an OpenCV index like 0.
--width WIDTH
                    Requested UVC capture width.
--height HEIGHT
                    Requested UVC capture height.
--fps FPS
                    Requested UVC capture FPS.
--fourcc FOURCC
                    Optional camera FOURCC request, for example MJPG or YUYV.
--buffer-size BUFFER_SIZE
                    Requested OpenCV capture buffer size. Use 0 to keep the backend default.
--output-width OUTPUT_WIDTH
                    ImageManip output width. Defaults to the requested capture width.
--output-height OUTPUT_HEIGHT
                    ImageManip output height. Defaults to the requested capture height.
--max-frames MAX_FRAMES
                    Stop after this many frames. Use 0 to run until interrupted.
--fps-log-interval FPS_LOG_INTERVAL
                    Print measured delivered FPS every N seconds. Use 0 to disable periodic logging.
--http-port HTTP_PORT
                    HTTP port used by the DepthAI Visualizer connection.
```

## Peripheral Mode

### Installation

Prepare a **Python >= 3.10** environment with the required packages:

```bash
pip install -r requirements.txt
```

### Examples

Run with automatic UVC detection:

```bash
python3 main.py
```

Run against a known Linux video node:

```bash
python3 main.py --uvc-device /dev/video2 --width 1920 --height 1080 --fps 5
```

Request MJPEG from a camera that supports higher Full HD frame rates:

```bash
python3 main.py --uvc-device /dev/video2 --width 1920 --height 1080 --fps 30 --fourcc MJPG
```

## Standalone Mode (RVC4 only)

Running in standalone mode runs the host node on the OAK device CPU. The `oakapp.toml` includes optional access to `/dev/video0` through `/dev/video9` so a UVC camera plugged into the OAK device can be opened from the container.

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Override the UVC device or format without editing the script:

```bash
oakctl app run . --env UVC_DEVICE=/dev/video2 --env UVC_WIDTH=1920 --env UVC_HEIGHT=1080 --env UVC_FPS=30 --env UVC_FOURCC=MJPG
```

## Notes

This example does not replace the physical onboard `Camera` sockets (`CAM_A`, `CAM_B`, etc.). It creates a host-produced `ImgFrame` stream that can be linked to compatible DepthAI nodes.
