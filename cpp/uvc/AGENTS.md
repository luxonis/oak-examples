# AGENTS.md

## Summary

This is the standalone-only C++ reference for turning an RVC4 device into a USB UVC camera. Use it when you need device-side USB gadget configuration and a C++ app that feeds video frames to a host as a standard UVC device instead of using the DepthAI Visualizer.

## Use This Example When

- You need the OAK device to appear as a standard USB camera on a host machine.
- You want a standalone-only C++ app that runs fully on RVC4.
- You need a reference for combining a DepthAI pipeline with the `uvc-gadget` framework.
- You need host UVC clients to adjust camera settings such as exposure mode, exposure time, brightness, or gain.
- You want to study the packaging and runtime requirements for configfs- and `/dev`-heavy OAK apps.

## Do Not Use This Example When

- You need host/peripheral Visualizer streaming.
- You need a minimal C++ pipeline with no Linux gadget setup.
- You need detections, models, or a browser frontend.
- You need a cross-platform host build flow as the primary use case.

## Quick Facts

- `Category:` `cpp/uvc`
- `Shape:` `cpp`
- `Primary task:` expose the device as a standalone USB UVC camera
- `Entrypoint:` [uvc-start.sh](uvc-start.sh)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; configfs and `/dev` access; `uvc-gadget` submodule content; USB gadget-capable runtime environment
- `Input:` one detected camera stream from the connected device camera list
- `Output:` continuous MJPEG UVC video stream plus MJPEG still-image responses over USB
- `Controls:` standard UVC auto-exposure mode, exposure time, brightness, and gain; optional extension-unit control for max ISO
- `Models:` none
- `Visualizer / UI:` none; the host sees a USB UVC camera

## Read First

- [src/uvc_example.cpp](src/uvc_example.cpp): full pipeline, UVC callback wiring, and stream lifecycle
- [src/uvc_example.hpp](src/uvc_example.hpp): UVC gadget header bridge
- [src/uvc_controls.cpp](src/uvc_controls.cpp): UVC control registration and mapping into `dai::CameraControl`
- [src/uvc_controls.hpp](src/uvc_controls.hpp): control registration interface shared with the main app
- [CMakeLists.txt](CMakeLists.txt): C++ build and `uvc-gadget` linkage
- [oakapp.toml](oakapp.toml): device permissions, mounts, build steps, and packaged runtime contract
- [uvc-start.sh](uvc-start.sh): configfs gadget setup, control and extension-unit advertisement, bind/unbind behavior, restart loop, and shutdown handling
- [README.md](README.md): standalone run instructions

## Architecture

- The app builds the `uvc-gadget` submodule, the local `uvc_example` binary, and the `src/uvc_controls.cpp` control bridge.
- [uvc-start.sh](uvc-start.sh) configures the USB gadget through configfs, advertises camera-terminal and processing-unit controls, optionally creates an extension unit, binds the UDC, and launches `/app/uvc_example`.
- The C++ app registers a buffer callback for the UVC gadget runtime.
- A `dai::Device` and `dai::Pipeline` are created on-device.
- The first detected connected camera is used as the video source.
- The camera creates a 1920x1080 MJPEG path for continuous UVC video and a 3840x2160 MJPEG path for still-image requests.
- `registerExampleControls(...)` binds host UVC control writes to `dai::CameraControl` messages on the camera input control queue.
- UVC stream on/off events call back into `depthai_control_pipeline_cb(...)`, which starts or stops camera streaming via `CameraControl`.

## Data Flow

- `device camera -> Camera node -> NV12 output -> MJPEG VideoEncoder -> outputQueue`
- `outputQueue -> depthai_uvc_get_buffer(...) -> UVC gadget buffers -> host USB UVC stream`
- `UVC stream events -> depthai_control_pipeline_cb(...) -> camera inputControl queue`
- `host UVC control write -> registerExampleControls(...) handlers -> camera inputControl queue`

## Modification Guide

- `Safe to change:` output resolution, still-image resolution, encoder profiles, UVC gadget strings, control defaults/ranges, restart-loop behavior, selected camera source
- `Requires care:` configfs gadget structure, UDC bind/unbind sequencing, advertised control selectors and extension-unit layout, allowed device mounts, C/C++ linkage with `uvc-gadget`, stream-on/stream-off control semantics
- `Likely to break if changed blindly:` USB gadget configuration, callback timing, keeping [uvc-start.sh](uvc-start.sh) and [src/uvc_controls.cpp](src/uvc_controls.cpp) in sync, library copy steps in [oakapp.toml](oakapp.toml), or runtime access to `/dev` and `/sys/kernel/config`

## Common Adaptations

- `To change the exported UVC mode:` edit `create_frame` usage in [uvc-start.sh](uvc-start.sh)
- `To change the camera resolution or format:` edit the `requestOutput(...)` and encoder setup in [src/uvc_example.cpp](src/uvc_example.cpp)
- `To change still-image behavior:` edit the still encoder path in [src/uvc_example.cpp](src/uvc_example.cpp) and the advertised still dimensions in [uvc-start.sh](uvc-start.sh)
- `To add or remove host-visible controls:` update the configfs-advertised `bmControls` and extension-unit setup in [uvc-start.sh](uvc-start.sh) together with the handlers in [src/uvc_controls.cpp](src/uvc_controls.cpp)
- `To support a different camera selection policy:` replace `device->getConnectedCameras()[0]` logic in [src/uvc_example.cpp](src/uvc_example.cpp)
- `To strip this back to a Visualizer-based C++ baseline:` compare against [cpp/camera_stream](https://github.com/luxonis/oak-examples/tree/main/cpp/camera_stream)

## Constraints

- This example is RVC4 standalone only.
- It depends on the `uvc-gadget` submodule being present and buildable.
- The runtime needs privileged-ish access patterns: writable configfs, `/dev` mounted into the container, and allowed device access.
- UVC control support depends on kernel configfs attributes being present; the extension-unit control is optional and is skipped when the kernel does not expose the needed extension path.
- The code currently selects the first connected camera only.
- The app pauses the DepthAI pipeline until the host starts the UVC stream.

## Non-Obvious Repo Conventions

- [uvc-start.sh](uvc-start.sh) is the real runtime entrypoint; [src/uvc_example.cpp](src/uvc_example.cpp) is only one part of the standalone behavior.
- The gadget setup is torn down and rebound on stop or restart, so gadget lifecycle is part of normal operation here.
- [uvc-start.sh](uvc-start.sh) and [src/uvc_controls.cpp](src/uvc_controls.cpp) are a matched pair: the shell script advertises controls in configfs, and the C++ file implements what those controls do.
- [oakapp.toml](oakapp.toml) copies shared libraries into `/usr/lib` manually after build; changing the build layout may require updating those copy steps.
- [oakapp.toml](oakapp.toml) builds against the `luxonis/depthai-library` image, so build/runtime assumptions should be checked there before changing dependencies.

## Related Examples

- [cpp/camera_stream](https://github.com/luxonis/oak-examples/tree/main/cpp/camera_stream): use this when you need the minimal C++ Visualizer baseline
- [streaming/on-device-encoding](https://github.com/luxonis/oak-examples/tree/main/streaming/on-device-encoding): use this when the main topic is encoded video flow rather than USB gadget mode
- [streaming/rtsp-streaming](https://github.com/luxonis/oak-examples/tree/main/streaming/rtsp-streaming): use this when you want network streaming instead of UVC over USB

## Validation

- `Run:` `git submodule update --init --recursive && oakctl app run .`
- `Success looks like:` the app configures the USB gadget, the host enumerates a UVC camera, and MJPEG video appears without custom host drivers
- `Common failure meaning:` the `uvc-gadget` submodule is missing, configfs or `/dev` access is unavailable, the UDC bind sequence fails, or the host never initiates UVC streaming
