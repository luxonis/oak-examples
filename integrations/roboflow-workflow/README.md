# Roboflow Workflow

This application integrates a DepthAI device with `Roboflow Workflow` through `inference` package. Camera frames are handed to Roboflow's `InferencePipeline` through a custom `VideoFrameProducer`, processed by the workflow's models directly on the device, and the results are sent to the DepthAI visualizer for real-time viewing. You can change the parameters of the inference pipeline through the interactive UI.

## Demo

![demo_output](media/output.gif)

## Usage

Before running this example, you’ll first need to create your own [Roboflow Workflow](https://roboflow.com/workflows/build) in the Roboflow web app ([documentation](https://docs.roboflow.com/workflows/create-a-workflow)).

Once your workflow is ready, populate the initial Roboflow settings in [config.yaml](./backend/src/config/yaml_configs/config.yaml).

To retrieve the required values:

- Open your workflow in Roboflow and click `Deploy`
- Choose `Video` -> `Live Video`
- Select `Run locally on my server or computer`
- In the provided code snippet, you’ll find:
  - `workspace_name`
  - `workflow_id`
- To get your `api_key`, go to `Settings` -> `API Keys` and copy your `Private API Key`
- The `workflow_parameters` correspond to the inputs defined on the `Inputs` node in your workflow.

At runtime, the custom frontend currently supports updating only:

- `api_key`
- `workspace_name`
- `workflow_id`
- `workflow_parameters`

Pipeline settings such as `device`, `output_size`, and `fps` still come from [config.yaml](./backend/src/config/yaml_configs/config.yaml) at startup.

> **Note:** You can update the supported Roboflow values later while the app is running using the custom front-end form. But you still need to start the app with some valid initial values.

## Workflow Visualization Rules & Limitations

Our system applies a few naming-based rules to determine how workflow outputs are visualized. Keep the following guidelines in mind:

#### 1. Outputs containing `predictions`

Outputs whose names include the substring `predictions` are treated as **DepthAI detection messages**. Only the bounding box information is processed; any additional fields in the Roboflow Detection message will be ignored.

If your workflow produces a `Roboflow Detection` message, ensure its output name includes `predictions` so it can be detected and parsed correctly.

#### 2. Outputs containing `visualization`

Outputs whose names include the substring `visualization` are interpreted as DepthAI ImgFrame messages.

If your workflow produces `Roboflow WorkflowImageData`, include `visualization` in the output name so we can display it properly.

#### 3. Outputs that do not match any rule

Outputs whose names do not contain either predictions or visualization are **ignored by the visualizer**.

#### Advanced Visualization Options

For richer or customized visual outputs, consider:

- Adding `Visualization` blocks directly inside your workflow and ensuring the resulting output name contains `visualization`.
- Extending the [AnnotationNode](./backend/src/core/annotation_node.py) with custom logic tailored to your data type.

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

Note: The app runs on the `python3.11` variant of the OakApp base image (`inference` supports Python `>=3.10,<3.13`). The backend sets `USE_INFERENCE_MODELS=False` so models are executed through the classic ONNX Runtime path of the `inference` package, which is considerably faster than the default torch-based backend on the device's ARM CPU.

## NPU (DSP) Inference

In standalone mode the workflow's ONNX models run on the OAK4's Hexagon DSP by default, through the ONNX Runtime QNN execution provider:

- [backend/src/core/qnn_patch.py](./backend/src/core/qnn_patch.py) reroutes the ONNX sessions created inside the `inference` package to [backend/src/oak4ort](./backend/src/oak4ort/), which bootstraps the DSP inside the app container and builds the QNN sessions.
- fp32 weights served by Roboflow run as **fp16 on the HTP** — no quantization or model changes needed. Dynamic batch dimensions are fixed to 1 automatically.
- The first load of a model compiles it for the HTP (can take tens of seconds); the compiled graph is cached (EPContext), so subsequent loads of the same downloaded weights are fast.
- Anything that cannot run on the DSP (unsupported ops, in-memory models, non-batch dynamic dims) transparently falls back to the CPU EP.

Environment toggles (see `[env]` in [oakapp.toml](./oakapp.toml)):

- `EP=dsp|cpu` — where to run the workflow's models (default `dsp`; `cpu` restores the previous behavior), e.g. `oakctl app run --env EP=cpu .`
- `STRICT=1` — fail instead of silently falling back to the CPU EP (useful to verify the DSP is actually used).

The DSP access is declared via the `optional_devices` / `optional_mounts` / `allowed_devices` block in [oakapp.toml](./oakapp.toml); on hosts without the DSP (e.g. running the backend locally) the app automatically stays on the CPU.
