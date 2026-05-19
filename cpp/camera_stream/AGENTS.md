# AGENTS.md

## Summary

This is the smallest C++ example in the repository. It is the best reference when you need the minimal `depthai::Pipeline` plus `dai::RemoteConnection` shape in C++, without any extra nodes, models, or frontend complexity.

## Use This Example When

- You need a C++ starting point for streaming camera frames to the Visualizer.
- You want the simplest example of creating a `dai::node::Camera` in C++.
- You need a baseline for building or packaging a C++ OAK app with CMake.
- You want a host/peripheral example that also has an RVC4 standalone packaging path.

## Do Not Use This Example When

- You need encoded video output, detections, or depth.
- You need a standalone-only device-mode app with no Visualizer.
- You need ROS, a custom frontend, or a multi-node pipeline.
- You need a richer C++ example with hardware-specific runtime behavior.

## Quick Facts

- `Category:` `cpp/camera_stream`
- `Shape:` `cpp`
- `Primary task:` minimal C++ camera streaming to DepthAI Visualizer
- `Entrypoint:` [src/main.cpp](src/main.cpp)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` `depthai-core` installed for host builds; a Luxonis device with a color camera on `CAM_A`
- `Input:` one RGB camera stream
- `Output:` one Visualizer topic named `stream`
- `Models:` none
- `Visualizer / UI:` DepthAI Visualizer via `dai::RemoteConnection`

## Read First

- [src/main.cpp](src/main.cpp): entire runtime pipeline
- [CMakeLists.txt](CMakeLists.txt): host build shape and `depthai::core` linkage
- [oakapp.toml](oakapp.toml): standalone build steps and `cpp` base image
- [backend-run.sh](backend-run.sh): packaged app startup command
- [README.md](README.md): host and standalone run instructions

## Architecture

- The app creates a `dai::RemoteConnection`.
- It creates one `dai::Pipeline`.
- A `dai::node::Camera` is bound to `CAM_A`.
- The app requests a `1280x800` `NV12` output from the camera.
- That output is registered as one Visualizer topic.
- The process stays alive until `q` is received through the RemoteConnection.

## Data Flow

- `CAM_A -> requestOutput(1280x800, NV12) -> RemoteConnection topic "stream"`

## Modification Guide

- `Safe to change:` topic name, output size, camera socket, key handling, CMake target name
- `Requires care:` camera socket assumptions, RemoteConnection lifecycle, host build environment for `depthai-core`
- `Likely to break if changed blindly:` switching to nodes that need extra libraries or assuming the standalone path behaves like a browser frontend app

## Common Adaptations

- `To add another topic:` request another output and register it in [src/main.cpp](src/main.cpp)
- `To change resolution or frame type:` edit the `requestOutput(...)` call in [src/main.cpp](src/main.cpp)
- `To use this as a packaged C++ baseline:` keep [CMakeLists.txt](CMakeLists.txt), [oakapp.toml](oakapp.toml), and [backend-run.sh](backend-run.sh), then expand only [src/main.cpp](src/main.cpp)
- `To move toward device-only USB streaming:` compare against [cpp/uvc](https://github.com/luxonis/oak-examples/tree/main/cpp/uvc)

## Constraints

- The example assumes the color camera is on `CAM_A`.
- The host build depends on a discoverable `depthai-core` installation.
- The packaged standalone path still uses `RemoteConnection`; it is not a headless device-mode app.
- Only one topic is published, so this is intentionally not a reusable multi-stream scaffold.

## Non-Obvious Repo Conventions

- [oakapp.toml](oakapp.toml) compiles the app inside the container during `build_steps`, not ahead of time.
- `assign_frontend_port = true` is present even though this is still a Visualizer topic flow, not a custom frontend.
- The README says to look for an `images` stream tile, but the actual topic name in code is `stream`.

## Related Examples

- [cpp/uvc](https://github.com/luxonis/oak-examples/tree/main/cpp/uvc): use this when you need standalone USB camera behavior instead of Visualizer streaming
- [tutorials/camera-demo](https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo): use this when a Python baseline is fine
- [apps/default-app](https://github.com/luxonis/oak-examples/tree/main/apps/default-app): use this when you want a richer packaged app with detections and depth

## Validation

- `Host run:` `cmake -S . -B build && cmake --build build && ./build/main`
- `Standalone run:` `oakctl app run .`
- `Success looks like:` the Visualizer shows a live topic named `stream`, and pressing `q` exits the app cleanly
- `Common failure meaning:` `depthai-core` is not discoverable by CMake, the device lacks the expected camera, or the Visualizer topic name is being looked up incorrectly
