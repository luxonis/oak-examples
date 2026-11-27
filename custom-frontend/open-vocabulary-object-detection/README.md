# Open Vocabulary Object Detection

This example demonstrates an advanced use of a custom frontend. On the DepthAI backend, it runs either **YOLOE** (default) or **YOLO-World** on-device, with configurable class labels and confidence threshold — both controllable via the frontend.
The frontend, built using the `@luxonis/depthai-viewer-common` package, displays a real-time video stream with detections.

> **Note:** This example works on RVC4 in peripheral or standalone mode and requires Luxonis OS 1.40 or newer.

## Demo

![open-vocabulary-object-detection](media/dynamic_yolo_world.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

Here is a list of all available parameters:

```
  -fps FPS_LIMIT, --fps_limit FPS_LIMIT
                        FPS limit for the model runtime. (default: None)
  -media MEDIA_PATH, --media_path MEDIA_PATH
                        Path to the media file you aim to run the model on. If not set, the model will run on the camera input. (default: None)
  -m {yolo-world,yoloe}, --model {yolo-world,yoloe}
                        Name of the model to use: yolo-world or yoloe (default: yoloe)
  --semantic_seg        Display output as semantic segmentation otherwise use instance segmentation (only applicable for YOLOE). (default: False)
```

Notes:

- The backend CLI currently supports `--fps_limit`, `--media_path`, `--model`, `--semantic_seg`, `--device`, and the frontend options below.
- Frontend serving is handled by the packaged oakapp container stack, so there are no active `--ip` or `--port` CLI options here.
- Model precision is currently controlled by the backend configuration files, not by a CLI flag.

### Model Options

This example supports two YOLO models:

- **YOLOE** (default): Supports both text prompts and image prompts (visual prompts). The model outputs 160 classes in total: indices 0–79 correspond to text prompts, and indices 80–159 correspond to image prompts. When only one prompt type is provided, dummy inputs are sent for the other and ignored by the model.
- **YOLO-World**: Open-vocabulary detection with text prompts and optional image prompting (CLIP visual encoder).

Notes:

- Backend function `extract_image_prompt_embeddings(image, max_num_classes=80, model_name, mask_prompt=None)` accepts an optional `mask_prompt` of shape `(80,80)` or `(1,1,80,80)` for `yoloe`. When `None`, a default central mask is used.

## Peripheral Mode (RVC4)

> Requirements pin depthai-nodes commit [`5df28b8`](https://github.com/luxonis/depthai-nodes/commit/5df28b8a65943eaf9fad74691e6cfc544728b189) for `serve_frontend`. Replace this pin with a release containing the helper before merging.

Use Python 3.12 and Node.js 22 or newer. From this example directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ..
python backend/src/main.py --device <DEVICE_IP>
```

Open `http://localhost:8082` on the host computer. Python serves the built custom
frontend and runs the backend; streams and controls use `RemoteConnection` on
port 8765. The frontend directory is resolved relative to the entrypoint.
Rebuild the frontend after changing its source.

Use `--frontend-dir` for another build directory, `--frontend-port` for another
HTTP port, or `--no-frontend` with a separate development server. The default
bind address is `127.0.0.1`; `--frontend-host` overrides it. Access from another
computer requires a separate HTTPS/WebSocket proxy.

Standalone mode keeps the existing oakapp frontend server. The Python helper
automatically skips its listener when that server is configured.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

This will run the example with default argument values (YOLOE model). If you want to change these values, edit the `entrypoint` in `oakapp.toml` to pass the arguments to the backend. Example:

```toml
entrypoint = ["/entrypoint.sh", "python3", "-u", "/app/backend/src/main.py", "--model", "yoloe", "--fps_limit", "10", "--semantic_seg"]
```

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail
