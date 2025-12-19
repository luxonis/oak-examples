# Dino Tracker

This application demonstrates interactive, similarity-based object tracking using FastSAM segmentation and DINO embeddings, running fully on-device with a live frontend for user interaction.

**It runs FastSAM + DINO on the DepthAI backend, and exposes controls in the UI for:**

- Selecting an object by clicking directly in the video stream
- Switching between semantic heatmap and bounding-box visualization
- Adjusting confidence threshold for similarity-based detections
- Toggling segmentation outlines for inspection and debugging

> **Note:** RVC4 standalone mode only.

![](media/DinoDemo.gif)

## Pipeline Graph

![](media/DinoGraph.png)

______________________________________________________________________

## Features

- **Interactive object selection**

  - Click on any region in the video stream
  - Selection drives similarity-based focus across frames
  - Clear selection at any time to reset tracking

- **Segmentation outlines (optional)**

  - Toggle FastSAM outlines to inspect segmentation results

- **Semantic similarity tracking**

  - Uses DINO embeddings to follow visually similar regions
  - No predefined classes required
  - Robust to appearance changes and partial occlusion

- **Visualization modes**

  - **Heatmap** – continuous similarity intensity
  - **Bounding boxes** – thresholded detection Bounding Boxes

- **Confidence control (BBox mode)**

  - Adjust threshold for converting similarity heatmaps into detections

- **Backend / frontend synchronization**

  - UI state is restored from the backend on connect
  - Backend remains authoritative over tracking state

- **Configuration (YAML constants)**

  - Core application parameters are defined in YAML files under the constants/ directory.
  - These files allow adjusting some constants used in the application without modifying the main codebase.

______________________________________________________________________

## Usage

Running this example requires a **Luxonis RVC4 device** connected to your computer.\
Refer to the [documentation](https://docs.luxonis.com/software-v3/) to set up your device if you haven't already.

______________________________________________________________________

## Standalone Mode (RVC4)

To run the example in standalone mode, first install the `oakctl` tool using the instructions [here:](https://docs.luxonis.com/software-v3/oak-apps/oakctl)

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

Remote access

You can upload oakapp to Luxonis Hub via oakctl
And then you can just remotely open App UI via App detail
