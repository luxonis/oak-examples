# AGENTS.md

This repository is a large reference corpus for building DepthAI and OAK applications. Use it to find the closest existing example before creating a new app or changing an existing one.

Start with [INDEX.md](INDEX.md). It is the agent-facing catalog of runnable/reference examples in this repository. The root [README.md](README.md) is still useful, but it is optimized more for human browsing than for fast agent retrieval.

## Navigation Order

1. Read this file.
2. Open [INDEX.md](INDEX.md) and shortlist the closest examples by task, modality, and example shape.
3. Open the target example's `AGENTS.md` first if it exists. These per-example files should be the primary agent entrypoint.
4. Then read that example's `README.md` for usage details, platform notes, and any caveats not repeated in `AGENTS.md`.
5. Inspect code in roughly this order:
   - `main.py` or `backend/src/main.py`
   - `oakapp.toml`
   - `backend-run.sh`
   - `utils/arguments.py`
   - `depthai_models/*.yaml`
   - `frontend/src/App.tsx` or `frontend/src/main.tsx`
   - `src/main.cpp` for C++ examples
     If the example uses a different layout, identify the real entrypoint and runtime config first, then follow the same idea: entrypoint, packaging/runtime config, support code, frontend if present.
     Also check for alternative entrypoints such as `host.py`, `oak.py`, ROS workspace packages under `src/`, launch files, or commands declared in `oakapp.toml`.
6. Reuse the closest task and pipeline logic first, then adapt the execution shape if needed.
   If multiple examples match, prefer the closest model or task first, then the closest execution shape.

## What This Repo Contains

- Many runnable/reference examples across multiple categories. This corpus will keep growing, so do not rely on any fixed count.
- Category overviews in `apps/`, `camera-controls/`, `cpp/`, `custom-frontend/`, `depth-measurement/`, `integrations/`, `neural-networks/`, `streaming/`, and `tutorials/`.
- Both minimal examples and production-shaped app layouts.
- Mixed host-driven, standalone, frontend/backend, ROS, and C++ workflows.

## Ignore These Paths

Do not treat these directories as source-of-truth examples unless you explicitly need them for a running example:

- `**/env/`
- `**/node_modules/`
- `**/dist/`
- `**/.depthai_cached_models/`
- `**/.cache/`
- `**/__pycache__/`
- `**/build/`
- `./.git/`
- `./.pytest_cache/`

Also ignore generated wheels, cached artifacts, and vendored site-packages unless the task is specifically about packaging or dependency debugging.

## Common Example Shapes

### 1. Simple Python example

Typical files:

- `main.py`
- `README.md`
- `requirements.txt`
- `utils/arguments.py`
- optional `oakapp.toml` for RVC4 standalone packaging

Use these when you need a compact reference for one pipeline or one focused feature.

### 2. Packaged Python app

Typical files:

- `main.py` or `backend/src/main.py`
- `oakapp.toml`
- `backend-run.sh`
- `README.md`

Use these when you need something closer to a deployable OAK app, especially for standalone RVC4 flows.

`oakapp.toml` is specifically about OAK app packaging and standalone deployment on RVC4. RVC2 devices do not run standalone OAK apps.
Its presence does not by itself mean the example is RVC4-only. Many examples with `oakapp.toml` are still valid references for RVC2 peripheral mode.

### 3. Frontend/backend app

Typical files:

- `backend/src/main.py`
- `frontend/src/App.tsx`
- `oakapp.toml`
- `backend-run.sh`
- frontend package files

Use these when the task needs a custom UI, two-way frontend/backend communication, or remote standalone access through the default oakapp container stack.

When the frontend/backend example relies on the default oakapp container stack for standalone deployment, that standalone path is an RVC4-only flow.

### 4. ROS app

Typical files:

- `oakapp.toml`
- ROS workspace files under `src/`
- package manifests / launch files / plugin code

Use these when the desired output is ROS topics, RViz visualization, or robot integration rather than the DepthAI Visualizer.

### 5. C++ example

Typical files:

- `CMakeLists.txt`
- `src/main.cpp` or another C++ entrypoint
- optional `oakapp.toml` for RVC4 standalone packaging

Use these when the task explicitly needs native C++ or a minimal `depthai-core` example.

## Common DepthAI Patterns In This Repo

- `dai.Device(...)` is usually created near the top of the entrypoint.
- `with dai.Pipeline(device) as pipeline:` is the main pipeline construction pattern.
- `dai.RemoteConnection(...)` is used for visualization and topic registration in many host-driven examples.
- `utils/arguments.py` usually defines the supported CLI knobs and often reveals what the example is intended to be varied by.
- `oakapp.toml` indicates that the example has an OAK app packaging path. In practice this is an RVC4 standalone concept, not an RVC2 runtime feature.
- Do not treat `oakapp.toml` as an exclusion signal for RVC2. Treat it as an additional standalone path unless the example docs explicitly say otherwise.
- `backend-run.sh` usually contains the effective backend command for standalone frontend/backend apps.
- `depthai_models/*.yaml` usually holds model descriptors that are more stable to reuse than ad hoc constants in code.

## How To Choose A Reference Quickly

If the task is:

- a minimal camera or viewer pipeline, start with `tutorials/camera-demo` or `cpp/camera_stream`
- a single-model inference flow, start with `neural-networks/generic-example`
- a packaged baseline application, start with `apps/default-app`
- a custom frontend or interactive UI, start with `custom-frontend/raw-stream` or `custom-frontend/open-vocabulary-object-detection`
- a depth or spatial pipeline, start in `depth-measurement/` or `neural-networks/object-detection/spatial-detections`
- a multi-device setup, start in `tutorials/multiple-devices/`
- a streaming protocol implementation, start in `streaming/`
- a ROS deployment, start in `apps/ros/`

## Reading Priorities Inside An Example

Read files in this order unless the layout suggests otherwise:

1. `AGENTS.md` if present
2. `README.md`
3. Entrypoint:
   - `main.py`
   - `backend/src/main.py`
   - `src/main.cpp`
   - `host.py` / `oak.py`
   - ROS workspace packages, launch files, or plugin entrypoints under `src/`
4. Runtime/config files:
   - `oakapp.toml`
   - `backend-run.sh`
   - `requirements.txt`
   - `package.json`
5. Support code:
   - `utils/*.py`
   - `depthai_models/*.yaml`
   - frontend components

## Exact Compatibility

Use `INDEX.md` to find the right example shape quickly. Use the example `README.md` and category `README.md` files for exact device/platform support, sensor assumptions, and runtime caveats.

Do not assume all examples support the same devices:

- some are RVC4-only
- some are standalone-only
- some require stereo cameras
- some require ToF
- some require thermal sensors
- some are host evaluation tools rather than deployable apps

## Non-Example Docs

These are useful, but they are not the main example corpus:

- [README.md](README.md): human-facing root overview
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution workflow
- `tests/`: test-specific material
- `.github/ci/`: CI and publishing support
- `custom-frontend/GETTING_STARTED.md`: frontend workflow guide

When a task is "build a new app", prefer the runnable example corpus in [INDEX.md](INDEX.md) over these support docs.

## Maintenance Rule

Whenever a new example is added, update [INDEX.md](INDEX.md) and add that example's `AGENTS.md`.
