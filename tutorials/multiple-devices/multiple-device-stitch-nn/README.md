# Multi device stitching with tiling and Yolo detection

Example **connects to multiple discoverable Luxonis cameras** of the same type (either RVC2 or RVC4) and **stitches their image streams into a single view**. It runs YoloV6-nano object detection on the resulting view by separating the wide image into tiles.

The browser visualizer shows the live stitched feed and detection overlays, providing a simple interface for monitoring and recalculation of homography.

At startup, the system calculates a homography between camera feeds to align them, and all subsequent warping is performed based on this fixed calibration. **Cameras are assumed to be static**; if they are moved, pressing “r” in the browser visualizer triggers a recalculation of the homography.

**Autofocus of all cameras is turned ON only some seconds** after start of program and after recalculation of homography, then it is turned OFF. This is to avoid the flickering in the resulting panorama image.

**Limitations:**

Cameras must be **vertically aligned** and have **sufficient field-of-view overlap** for reliable stitching. The **image order (left to right) is important** and should remain consistent across runs. For best results, **use identical, well-calibrated cameras**, as differences in lens parameters or image quality can negatively impact stitching and homography accuracy.

Stitching, tiling and YOLO detections run on host computer can be **costly on the processing resources** - especially with larger number of cameras connected - and the output FPS will depend on the host CPU power. If output FPS is too low, **try lowering the resolution** with `--input_size` parameter.

This example is intended as a conceptual demonstration rather than a production-ready implementation. It provides a foundation for users to extend and refine as needed.

## Demo

![example](media/stitching.gif)

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

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).
- [Stitching](https://pypi.org/project/stitching/)

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This will run the Stitching with YOLO detection example with all the discoverable devices.

```bash
python3 main.py -fps 10
```

This will run the example at 10 FPS.

```bash
python3 main.py -is 720p
```

This will run the example with resolution 720p.

## FAQ

**Why aren’t the images stitching correctly (e.g., strange wrapping or distortion)?**

Ensure that your cameras are ordered correctly from left to right, vertically aligned, and positioned as close together as possible. While focused on the web visualizer (http://localhost:8082), press "r" to recalculate the homography. Once you find the right camera order you will see a well stitched image.

**Why are two separate (concatenated) images shown instead of a stitched one?**

This usually means there isn’t enough field-of-view (FOV) overlap between cameras.
Try adjusting their positions to increase the overlap until stitching occurs.
Additionally, ensure that:

- Your cameras are ordered correctly from left to right, vertically aligned, and positioned as close together as possible
- Both camera streams have similar lighting conditions (avoid direct sunlight exposure).
- The camera lenses are clean, as smudges or fingerprints can prevent reliable keypoint detection needed for stitching.

**Why is the panorama image blurry?**

Autofocus is turned automatically off after some seconds to avoid flickering. It may be that for your setup, autofocus needs more time. Try pressing "r" in the web visualizer (http://localhost:8082) to recalculate homography and reset autofocus. If result is still problematic, try making `AF_MSG_DELAY_S` bigger to allow more time for autofocus. Also make sure cameras are clean as smudges or fingerprints can result in blurry images.
