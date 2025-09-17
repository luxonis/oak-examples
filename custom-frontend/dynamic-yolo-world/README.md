# Dynamic YOLO World/YOLOE

This example demonstrates an advanced use of a custom frontend. On the DepthAI backend, it runs either the **YOLO-World** (default), **YOLOE**, or **YOLOE-Image** model on-device, with configurable class labels and confidence threshold — both controllable via the frontend.
The frontend, built using the `@luxonis/depthai-viewer-common` package, displays a real-time video stream with detections. It is combined with the [default oakapp docker image](https://hub.docker.com/r/luxonis/oakapp-base), which enables remote access via WebRTC.

> **Note:** This example works only on RVC4 in standalone mode.

## Demo

![dynamic-yolo-world](media/dynamic_yolo_world.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

Here is a list of all available parameters:

```
-fps FPS_LIMIT, --fps-limit FPS_LIMIT
					FPS limit. (default: None)
-ip IP, --ip IP       IP address to serve the frontend on. (default: None)
-p PORT, --port PORT  Port to serve the frontend on. (default: None)
-m MODEL, --model MODEL
					Name of the model to use: yolo-world, yoloe, or yoloe-image (default: yolo-world)
--precision PRECISION
					Model precision for YOLOE models: int8 (faster) or fp16 (more accurate) (default: int8)
```

### Model Options

This example supports three different YOLO models:

- **YOLO-World** (default): Open-vocabulary detection with text prompts and optional image prompting (CLIP visual encoder).
- **YOLOE**: Fast detection with enhanced visualization, including instance segmentation. Only text prompts are supported.
- **YOLOE-Image**: Visual-prompt-only variant of YOLOE. Uses a visual prompt encoder to extract embeddings from an image mask and applies them as class features. If no mask is provided, a default central mask is used. Visual encoder reference: [YOLOE visual encoder ONNX](https://huggingface.co/sokovninn/yoloe-v8l-seg-visual-encoder/blob/main/yoloe-v8l-seg_visual_encoder.onnx).

Notes:

- Backend function `extract_image_prompt_embeddings(image, max_num_classes=80, model_name, mask_prompt=None)` accepts an optional `mask_prompt` of shape `(80,80)` or `(1,1,80,80)` for `yoloe-image`. When `None`, a default central mask is used.

### Prerequisites

Before running the example you’ll need to first build the frontend. Follow these steps:

1. Install FE dependencies: `cd frontend/ && npm i`
2. Build the FE: `npm run build`
3. Move back to origin directory: `cd ..`

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

This will run the example with default argument values (YOLO-World model). If you want to change these values you need to edit the `backend-run.sh` file to pass the arguments to the backend. Example:

```bash
python3.12 /app/backend/src/main.py --model yoloe --precision fp16 --fps-limit 10
```

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail
