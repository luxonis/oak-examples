# Person Distances and Bird's-Eye View

This example runs the [SCRFD person detector](https://models.luxonis.com/luxonis/scrfd-person-detection/c3830468-3178-4de6-bc09-0543bbe28b1c) with automatically selected depth, measures the 3D distance between every pair of people with valid depth, and displays their positions in the standard DepthAI Visualizer. It has no custom frontend or proximity alert.

The Visualizer shows four topics:

- `Video`: the camera image.
- `Detections`: detected people and the SCRFD model's five keypoints on the camera image.
- `Pairwise distances`: tracked boxes and IDs, plus lines and 3D distances between every pair of people with valid depth on the camera image.
- `Bird's-eye view`: camera-relative X/Z person positions with the same track IDs on a 960 × 720 canvas. A single line highlights the closest visible pair, with both IDs and their distance in the header.

The view plots X to the right and Z forward from the camera, up to 7.5 m on either side and 15 m ahead. This gives both axes the same scale. Distances use all three spatial coordinates (X/Y/Z), so their values may differ from distances estimated from the 2D plot. This is a camera-relative projection, not a floor-aligned map; a tilted camera changes what the plot represents. The tracker assigns IDs across frames; the `Pairwise distances` overlay shows an ID for each active track, while invalid depth and positions outside the displayed range are omitted from the bird's-eye view. A single detected person produces no pairwise distance line.

> **Note:** This example requires a color camera and a depth backend supported by `dai.node.Depth`. The depth output is aligned to the color stream; `Depth.Algorithm.AUTO` selects the backend for the device.

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

You can run the example fully on device ([`STANDALONE` mode](#standalone-mode-rvc4-only)) or using your computer as host ([`PERIPHERAL` mode](#peripheral-mode)).

Here is a list of all available parameters:

```
-d DEVICE, --device DEVICE
                      Optional name, DeviceID or IP of the camera to connect to. (default: None)
-fps FPS_LIMIT, --fps_limit FPS_LIMIT
                      FPS limit for the model runtime. (default: 10 for both RVC2 and RVC4)
```

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.12** environment (recommended) with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [DepthAI Nodes](https://pypi.org/project/depthai-nodes/).

You can simply install them by running:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer and there will be communication between device and host which could affect the overall speed of the app. Below are some examples of how to run the example.

### Examples

```bash
python3 main.py
```

This will run the example with default arguments.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This will run the example with default argument values. If you want to change these values you need to edit the `oakapp.toml` file (refer [here](https://docs.luxonis.com/software-v3/oak-apps/configuration/) for more information about this configuration file).
