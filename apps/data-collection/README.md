# Data Collection

This application combines on-device open-vocabulary detection with an interactive frontend to **auto-collect “snaps” (images + metadata) under configurable conditions**.\
It runs **YOLOE** on the DepthAI backend, and exposes controls in the UI for:

- Selecting labels (by **text** or **image prompt**)
- Adjusting **confidence threshold**
- Enabling **snap conditions** (timed, no detections, low confidence, lost-in-middle)

> **Note:** RVC4 standalone mode only.


![](https://github.com/luxonis/oak-examples/blob/hub_snapping/apps/data-collection/media/data_collection_app_demo.gif)



## Features

- **Class control**
  - Update classes by text or upload an image to create a visual prompt
- **Confidence filter**
  - Drop detections below a chosen threshold
- **Snapping (auto-capture)**
  - **Timed** (periodic)
  - **No detections** (when a frame has zero detections)
  - **Low confidence** (if any detection falls below threshold)
  - **Lost-in-middle** (object disappears inside central area; edge buffer configurable)
  - Cooldowns **reset** when snapping is (re)started

______________________________________________________________________

## Usage

A **Luxonis device** (RVC4) is required

______________________________________________________________________

## Standalone Mode (RVC4)

Install `oakctl` (see [docs](https://docs.luxonis.com/software-v3/oak-apps/oakctl)), then:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail -->
