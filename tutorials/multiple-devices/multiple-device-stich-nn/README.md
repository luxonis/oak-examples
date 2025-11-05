# Multi device stitching with tiling and Yolo detection

multiple-device-stitch-nn connects to multiple discoverable DepthAI cameras of the same type (either RVC2 or RVC4) and stitches their image streams into a single view. At startup, the system calculates a homography between camera feeds to align them, and all subsequent warping is performed based on this fixed calibration. Cameras are assumed to be static; if they are moved, pressing “r” in the browser visualizer triggers a recalculation of the homography.

The stitched image is processed by the YOLOv6-nano model for object detection. To handle large panoramic views efficiently, the stream is tiled into smaller sections for inference, and detections from all tiles are then merged into a unified output. The browser visualizer shows the live stitched feed and detection overlays, providing a simple interface for monitoring and recalibration.

## Demo

TODO gif

## Usage

Running this example requires at least two **Luxonis devices** connected to your computer or on the same network. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your devices if you haven't done it already.

You can only run the example in [`PERIPHERAL` mode](#peripheral-mode) (using your computer as host).

Here is a list of all available parameters:

```
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                    FPS limit for the model runtime. (default: 20)
-is INPUT_SIZE, --input_size INPUT_SIZE
                    Input video stream resolution. {2160p, 1080p, 720p, 480p, 360p} (default: 360p)
```

## Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).
- [Stitching](https://pypi.org/project/stitching/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

## Examples

```bash
python3 main.py
```

This will run the Stitching with YOLO detection example with the default device and camera input.

```bash
python3 main.py -fps 10
```

This will run the example at 10 FPS.

```bash
python3 main.py -is 720p
```

This will run the example with resolution 720p from the cameras. Sitching, tiling and YOLO detections can be costly on the processing resources - especially with larger number of cameras connected - and the output FPS will depend on the CPU power. If output FPS are too low, try lowering the resolution.