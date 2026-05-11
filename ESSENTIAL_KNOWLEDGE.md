# ESSENTIAL_KNOWLEDGE.md

Shared vocabulary and repository concepts for agents working in `oak-examples`.

## Official Docs

Use these when an example guide or source code is not enough. Prefer the narrowest relevant page instead of broad documentation browsing.

- [DepthAI](https://docs.luxonis.com/software-v3/depthai.md): SDK/API overview for building OAK pipelines in Python or C++.
- [Device](https://docs.luxonis.com/software-v3/depthai/depthai-components/device.md), [Pipeline](https://docs.luxonis.com/software-v3/depthai/depthai-components/pipeline.md), and [Nodes](https://docs.luxonis.com/software-v3/depthai/depthai-components/nodes.md): core DepthAI runtime concepts.
- [Host Nodes](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes.md): host-side processing inside a DepthAI pipeline.
- [OAK Apps](https://docs.luxonis.com/software-v3/oak-apps.md): standalone application model for OAK devices.
- [oakctl](https://docs.luxonis.com/software-v3/oak-apps/oakctl.md): CLI for managing OAK devices and deploying/managing OAK Apps.
- [oakapp.toml configuration](https://docs.luxonis.com/software-v3/oak-apps/configuration.md): OAK App configuration file reference.
- [AI inference](https://docs.luxonis.com/software-v3/ai-inference.md), [Model Zoo](https://docs.luxonis.com/software-v3/ai-inference/model-source/zoo.md), [NN Archive](https://docs.luxonis.com/software-v3/ai-inference/nn-archive.md), and [conversion](https://docs.luxonis.com/software-v3/ai-inference/conversion.md): model selection, packaging, and conversion concepts.
- [RVC2](https://docs.luxonis.com/hardware/platform/rvc/rvc2.md) and [RVC4](https://docs.luxonis.com/hardware/platform/rvc/rvc4.md): hardware platform background.

## Devices And Platforms

- `OAK` or `Luxonis device` means a DepthAI-compatible Luxonis camera/device.
- `RVC2` devices run examples from a host computer in peripheral mode. They do not run standalone OAK Apps on-device.
- `RVC4` devices can run host/peripheral examples and can also run standalone OAK Apps when an example supports that packaging path.
- Do not infer exact compatibility from directory names or `oakapp.toml` alone. Use the selected example guide, runtime files, and code.
- Some examples require specific hardware such as stereo cameras, ToF, thermal sensors, IMU, autofocus, or multiple devices.

## Execution Modes

- `host` or `peripheral` means Python/C++ code runs on the host computer and communicates with the OAK device.
- `standalone` means the app is packaged and run on an RVC4 device as an OAK App.
- `oakctl` is the main CLI to know about for standalone workflows: use it to interact with devices and deploy/manage OAK Apps.
- `host + standalone` means the same example has a host/peripheral workflow and an RVC4 standalone packaging path.
- `standalone-only` means standalone deployment is the intended workflow; these examples are usually RVC4-focused.
- `multi-device host` means a host-driven workflow that connects to more than one OAK device.

## Common Runtime Files

- `main.py` is the usual Python entrypoint for simple examples.
- `backend/src/main.py` is the usual backend entrypoint for frontend/backend apps.
- `src/main.cpp` is the usual C++ entrypoint.
- `oakapp.toml` is the OAK App configuration file. Its presence means the example has a standalone packaging path, not that host/peripheral use is impossible.
- `backend-run.sh` often contains the effective backend command used in standalone frontend/backend apps.
- `utils/arguments.py` usually defines CLI options and reveals which parts of the example are intended to vary.
- `depthai_models/*.yaml` often contains model descriptors. Prefer these over copying hardcoded model constants when reusing default model setup.

## Common DepthAI Concepts

- `dai.Device(...)` connects to an OAK device.
- `with dai.Pipeline(device) as pipeline:` is the common pipeline construction pattern in these examples.
- A pipeline is composed of nodes such as cameras, stereo depth, neural networks, host nodes, encoders, and visualization helpers.
- `dai.RemoteConnection(...)` is commonly used to expose streams, topics, services, and the DepthAI Visualizer.
- The `Visualizer` displays registered topics such as frames, detections, depth maps, overlays, and annotations.
- `HostNode` means processing runs on the host side inside the DepthAI pipeline structure, not on-device compute.

## Models And Inference

- `HubAI`, `Model Zoo`, and model slugs refer to downloadable Luxonis models, for example `luxonis/yolov6-nano:r2-coco-512x288`.
- `NNArchive` packages model metadata and artifacts for DepthAI runtime use.
- `ParsingNeuralNetwork` runs a model and emits parsed outputs when the model descriptor supports parsing.
- Not every model is available for every platform. Check the model descriptor, selected platform, and runtime errors before assuming support.
- Generic single-model examples are not automatically valid for multi-input, multi-head, multi-stage, or host-decoded models.

## Frontend And Backend Apps

- `frontend` examples combine a Python backend with a web UI.
- `frontend/src/App.tsx` or `frontend/src/main.tsx` usually contains the main UI wiring.
- Frontend/backend examples may use services for two-way UI/backend communication.
- Some frontend apps serve static files directly; others rely on the OAK App container stack or WebRTC for standalone access.
- Keep backend service names, topic names, and frontend consumers aligned when modifying these examples.
