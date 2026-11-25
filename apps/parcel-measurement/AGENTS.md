# AGENTS.md

## Summary

OAK4 parcel measurement with public depthai-nodes detection, dimensioning, and support-plane calibration. A standard OAK App frontend displays H.264 RGB with native tracking and dimension annotations and lets the operator select the support surface.

## Use This Example When

- You need parcel measurement on a user-selected horizontal support plane.
- You need RGB boxes labelled with tracking IDs and length, width, and height.
- You need the evaluated capture profile from depthai-nodes PR 348.
- You need a frontend app with service controls and event-driven pipeline host nodes.

## Do Not Use This Example When

- You need persistent parcel identity across occlusion or cameras.
- You need RVC2, arbitrary object segmentation, or point-to-point measurement.
- You need guaranteed measurement accuracy without a scene-specific evaluation.

## Quick Facts

- `Category:` `apps/parcel-measurement`
- `Shape:` `frontend`
- `Entrypoint:` [main.py](main.py), pipeline lifetime, services, and topic publication
- `Pipeline:` [pipeline.py](pipeline.py), all capture, calibration, measurement, encoding, and benchmark nodes
- `Host nodes:` [nodes.py](nodes.py), `ParcelController` and `BenchmarkLogger`
- `Geometry:` [geometry.py](geometry.py) and [rendering.py](rendering.py)
- `Domain state:` [domain.py](domain.py), calibration lifecycle and tracking
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx), React and Luxonis `DepthAIContext` and `Streams`
- `Frontend hosting:` [oakapp.toml](oakapp.toml), static build and the base image's HTTPS proxy, port 8000 by default
- `Mode:` host plus OAK4 standalone packaging
- `Requires:` OAK4 RGB, stereo, processed accelerometer reports, Python 3.12, and Node.js 24 for the frontend build
- `Capture:` 10 FPS, unrectified RGB 2000 × 1500 NV12 and left and right 1280 × 800 GRAY8
- `Depth:` NeuralDepth LARGE at 768 × 480, native organized PointCloud on host
- `Topics:` `Color stream` as H.264 and `Parcel annotations` as native `ImgAnnotations`, in the `preview` group
- `Dependencies:` [requirements.txt](requirements.txt), immutable depthai-nodes PR 348 revision with parcel and box-measurement extras

## Read First

- [pipeline.py](pipeline.py) for public node wiring and stream configuration.
- [nodes.py](nodes.py) for event handling, service commands, scene admission, and result joins.
- [rendering.py](rendering.py) and [geometry.py](geometry.py) for frame metadata, previews, and native annotations.
- [frontend/src/services.ts](frontend/src/services.ts) for the shared frontend service contract.
- [oakapp.toml](oakapp.toml) for the static frontend build and runtime dependencies.
- [README.md](README.md) for operation and scene requirements.

## Architecture

One device-backed pipeline creates every node before startup. Camera outputs retain the evaluated unrectified grids and native metadata. NeuralDepth emits 768 × 480 depth. PointCloud produces organized XYZ in the common calibration reference frame.

`ParcelController` is a `ThreadedHostNode`. Its blocking `MessageQueue.getAny` dispatches scene, IMU, calibration, detection, measurement, and command inputs. Service callbacks enqueue commands or read locked state snapshots. `main.py` only manages pipeline tasks, remote key input, and shutdown. It does not poll application data queues.

`SupportPlaneCalibrator` receives the organized native cloud. The controller rotates processed accelerometer specific force from RGB optical axes into the common reference, without negation. Calibration candidates retain a generation so stale selections can be rejected.

The detector builds without a support plane. The controller admits a parcel scene after selection and sends `ParcelDetectorConfig` immediately before that scene. Later selections use the same config input. One scene remains in flight, retaining its RGB frame until detection and measurement results join by cloud sequence. Old calibration generations cannot publish new overlays.

The controller publishes the matching native NV12 RGB frame to the H.264 encoder and native `ImgAnnotations` to the frontend. Annotations copy the color frame's sequence, timestamps, and transformation. Candidate previews are separate JPEG still images, fetched once per candidate generation. Depth is internal and is not published as a frontend topic.

`BenchmarkLogger` is a host node with a timed blocking wait. It counts actual detector and dimensioner outputs and consumes the two host `BenchmarkIn` report streams. It prints ten-second summaries even while the detector waits for its first plane.

The React frontend uses the same Luxonis viewer, service hooks, and static build pattern as the other apps. `getParcelState` returns state without preview images. `calibrateSupportPlane` starts calibration, `selectSupportPlane` accepts `{generation, index}`, and `getSupportPlanePreview` accepts the same candidate key and returns `{jpeg}`. The base image serves the compiled frontend and proxies `/dai` to `RemoteConnection`.

## Constraints

- Import only names exported by `depthai_nodes.node` and `depthai_nodes.message` at runtime. Do not import frozen algorithms or node implementation internals.
- Standalone packaging uses `luxonis/oakapp-base:1.3.0` and Python 3.12. Keep `/entrypoint.sh` and the `static_frontend` build so the base image serves the frontend. Do not restore a bespoke Python HTTP server or JPEG video WebSocket path.
- Keep `libgfortran5` and `libegl1` in the container dependencies; the ARM64 Open3D wheel requires them even without a GUI.
- Keep the DepthAI 3.12.0 pin aligned with the pinned depthai-nodes revision. The OAK4 visibility implementation has no custom native kernels; do not restore the old `build_native` step or compiler dependency.
- Parcel messages stay in one host process. They have no XLink or RemoteConnection serialization. Publish native encoded frames and annotations instead.
- Keep PointCloud DEFAULT coordinates, millimeters, calibrated translation, identity custom transform, and organized output. XYZ already occupies the common reference. Do not apply its source optical pose again.
- The calibration cloud stays organized to 768 × 480. Detector input contains only finite, nonzero XYZ and retains its native metadata.
- Keep raw RGB and mono inputs unrectified. Do not substitute NeuralDepth's rectified views or resize detector inputs.
- Capture defaults to 10 FPS. Video follows matching measurement frames after plane selection. The frontend reports capture and measurement rates separately.
- Keep native annotation metadata aligned to the displayed color frame, including its independent sequence counter. Use the delivered intrinsics, distortion, and pose for projection.
- Keep both `BenchmarkIn` sinks on the host. Count outputs and failures independently of native report cadence. `latency_samples` describes sampled cumulative capture-to-output latency, not isolated node execution time.
- Keep the camera fixed after plane selection. Recalibrate whenever the camera or support surface moves.
- Calibration attempts cannot overlap. Candidate selection carries a generation to reject stale clicks.
- Candidate IDs are frame-local. Never display them as temporal tracking IDs without the app's association step.
- Failed frames, no-fit results, and unknown heights are distinct outcomes. Do not replace missing dimensions with zeros.
- Keep local scene images under ignored `evidence/`.

## Related Examples

- [apps/box-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/box-measurement) for the static frontend, service controls, and support-plane workflow.
- [apps/onnxruntime-track-anything](https://github.com/luxonis/oak-examples/tree/main/apps/onnxruntime-track-anything) for matched H.264 video and native annotations.
- [apps/p2p-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/p2p-measurement) for frontend services and pipeline host nodes.
- [neural-networks/depth-estimation/neural-depth](https://github.com/luxonis/oak-examples/tree/main/neural-networks/depth-estimation/neural-depth) for native NeuralDepth configuration.

## Validation

- Run `python3 -m unittest discover -s tests -v` and `npm --prefix frontend run build` in this directory.
- Run `oakctl app run .`, open the printed HTTPS frontend URL, trigger support-plane calibration, inspect previews, and select the true supporting surface.
- Confirm matching H.264 RGB and native boxes with tracking IDs and dimensions. Recalibrate and verify that measurement resumes without restarting the pipeline.
- Inspect `Color stream` and `Parcel annotations` with oakctl. Depth is internal. Process startup alone does not validate measurement.
- Confirm idle and active ten-second benchmark log summaries for both parcel stages.
- Use `--evidence evidence` to save metadata, the selected plane, RGB, overlay, and structured results locally.
- See [VALIDATION.md](VALIDATION.md) for completed checks and their limits. Earlier custom-server evidence does not validate the current frontend transport.
