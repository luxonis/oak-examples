# AGENTS.md

## Summary

OAK4 object measurement with public depthai-nodes detection, dimensioning, and support-plane calibration. A standard OAK App frontend displays H.264 RGB with native tracking and dimension annotations and lets the operator select the support surface.

## Use This Example When

- You need object measurement on a user-selected horizontal support plane.
- You need RGB boxes labelled with tracking IDs and length, width, and height.
- You need the evaluated capture profile from depthai-nodes PR 348.
- You need a frontend app with service controls and event-driven pipeline host nodes.

## Do Not Use This Example When

- You need persistent object identity across occlusion or cameras.
- You need RVC2, arbitrary object segmentation, or point-to-point measurement.
- You need guaranteed measurement accuracy without a scene-specific evaluation.

## Quick Facts

- `Category:` `apps/measure-anything`
- `Shape:` `frontend`
- `Entrypoint:` [main.py](main.py), pipeline lifetime, services, and topic publication
- `Pipeline:` [pipeline.py](pipeline.py), all capture, calibration, measurement, encoding, and benchmark nodes
- `Host nodes:` [nodes.py](nodes.py), `MeasurementController` and `BenchmarkLogger`
- `Preview worker:` [preview.py](preview.py), calibrated overlay remapping and paired video/annotation output
- `Geometry:` [geometry.py](geometry.py) and [rendering.py](rendering.py)
- `Domain state:` [domain.py](domain.py), calibration lifecycle and tracking
- `Measurement history:` [history.py](history.py), durable snapshots and scheduling; [storage_node.py](storage_node.py), asynchronous writer; [snapshot.py](snapshot.py), public message extraction
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx), React and Luxonis `DepthAIContext` and `Streams`
- `Frontend hosting:` [oakapp.toml](oakapp.toml), static build and the base image's HTTPS proxy, port 8000 by default
- `Mode:` host plus OAK4 standalone packaging
- `Requires:` OAK4 RGB, stereo, processed accelerometer reports, Python 3.12, and Node.js 24 for the frontend build
- `Capture:` 10 FPS, unrectified RGB 2000 × 1500 NV12 and left and right 1280 × 800 GRAY8
- `Depth:` unified `Depth.build(fps=10)` with SDK defaults, ImageAlign to an undistorted 768 × 480 RGB branch, public ImageAlignDepthCorrection, then native organized PointCloud
- `Topics:` `Color stream` as H.264 and `Object annotations` as native `ImgAnnotations`, in the `preview` group
- `Dependencies:` [requirements.txt](requirements.txt), immutable depthai-nodes PR 348 revision with `measure-anything` and `box-measurement` extras

## Read First

- [pipeline.py](pipeline.py) for public node wiring and stream configuration.
- [nodes.py](nodes.py) for event handling, service commands, scene admission, and result joins.
- [rendering.py](rendering.py) and [geometry.py](geometry.py) for frame metadata, previews, and native annotations.
- [frontend/src/services.ts](frontend/src/services.ts) for the shared frontend service contract.
- [oakapp.toml](oakapp.toml) for the static frontend build and runtime dependencies.
- [README.md](README.md) for operation and scene requirements.

## Architecture

One device-backed pipeline creates every node before startup. Detector images retain the unrectified grids and native metadata. A separate RGB output is undistorted and stretched to 768 × 480 for ImageAlign's target geometry. The unified `Depth` node is built with only the FPS argument and supplies native depth to ImageAlign. Keep algorithm, model, and source resolution at SDK defaults; log the resolved algorithm/configuration in the capture profile. The public `ImageAlignDepthCorrection` consumes `outputAligned` and the same node's exact `passthroughInput` with policy `source_axial_requires_correction`. Its corrected target-axial RAW16 output feeds PointCloud. Host Sync retains the matching structured correction result alongside corrected depth, native organized cloud, and raw images.

`read_scene` validates the depth, cloud, and correction frame identity. It zeros rows for invalid RAW16 depth or nonfinite XYZ, preserving organized layout. The controller's `calibration_cloud` output supplies that sanitized organized cloud to SupportPlaneCalibrator. The detector receives its finite nonzero rows. Correction provenance travels with SceneFrame, state, startup logs, and saved measurement details.

`MeasurementController` is a `ThreadedHostNode`. Its blocking `MessageQueue.getAny` dispatches scene, IMU, calibration, detection, measurement, and command inputs. Service callbacks enqueue commands or read locked state snapshots. `main.py` only manages pipeline tasks, remote key input, and shutdown. It does not poll application data queues.

`SupportPlaneCalibrator` receives the organized native cloud. The controller rotates processed accelerometer specific force from RGB optical axes into the common reference, without negation. Calibration candidates retain a generation so stale selections can be rejected. Every five seconds, the controller sends public `SupportPlaneCalibrationControl.verify` and consumes `verificationOutput`. Only one verification is pending. Generation, plane, and source sequence guard stale replies. Rejection expires the selected plane, stops admission, invalidates pending previews/results, and prompts recalibration in the frontend.

The detector builds without a support plane. The controller admits object scenes after selection and sends `MeasureAnythingDetectorConfig` immediately before the first scene. Later selections use the same config input. At most two scenes remain in flight to absorb timing jitter, retaining RGB until detection and measurement results join by cloud sequence. Recalibration keeps old jobs in those slots until they complete, then rejects their results. Sequence regression cannot rewind tracking or video. This measurement bound is separate from the single in-flight storage job.

The controller sends preview jobs to `PreviewRendererNode`, whose size-one nonblocking queue keeps the latest waiting frame. The worker emits paired native NV12 RGB and `ImgAnnotations`, retaining the color sequence, timestamps, and transformation. It drops stale-generation work before and after rendering. RGB decoding is lazy; normal RGB preview passes the original NV12 frame directly to the H.264 encoder. Candidate previews are separate JPEG still images, fetched once per candidate generation. Depth stays internal.

`BenchmarkLogger` is a host node with a timed blocking wait. It counts actual detector and dimensioner outputs and consumes the two host `BenchmarkIn` report streams. It prints ten-second summaries even while the detector waits for its first plane.

The React frontend uses the same Luxonis viewer, service hooks, and static build pattern as the other apps. `getMeasurementState` returns state without preview images. `calibrateSupportPlane` starts calibration, `selectSupportPlane` accepts `{generation, index}`, and `getSupportPlanePreview` accepts the same candidate key and returns `{jpeg}`. The base image serves the compiled frontend and proxies `/dai` to `RemoteConnection`.

`MeasurementStore` uses SQLite in `OAKAGENT_STORAGE_APP` or the local ignored `data/` directory. Startup loads at most 20 summaries and the tracking ID high-water mark. `SaveScheduler` owns saved, waiting, update-requested, and busy state. The controller sends one immutable segmented-cloud reference and small metadata through `history_jobs`. `StorageHostNode` performs encoding and the transaction, then acknowledges success or failure. No further snapshot is submitted until acknowledgement, and no sequence can submit twice. Waiting IDs keep their first-seen order; evicted IDs remain marked saved for the current run.

`getMeasurements` returns cached summaries and current visibility. `getMeasurement` reads a single detail record on the service thread. `requestMeasurementUpdate` accepts `{track_id}` and schedules a later sequence only while the object remains visible. SQLite replaces the previous cloud and metadata atomically. New tracks after restart use fresh IDs rather than overwriting historical records.

`setPreviewOptions` accepts `{depth, support_plane}` booleans. The preview worker caches the calibrated raw-RGB-to-undistorted-depth remap by full delivered geometry. It requires a shared RGB optical center, selects either the public colormap output or the plane-only texture on the depth grid, and uses OpenCV remapping and masked blending. Do not restore per-frame full-cloud reprojection or raw depth resizing. The Measurements modal uses Three.js to display the cloud and cuboid in the same transformed coordinate frame.

## Constraints

- Import only names exported by `depthai_nodes.node` and `depthai_nodes.message` at runtime. Do not import frozen algorithms or node implementation internals.
- Standalone packaging uses `luxonis/oakapp-base:1.3.0` and Python 3.12. Keep `/entrypoint.sh` and the `static_frontend` build so the base image serves the frontend. Do not restore a bespoke Python HTTP server or JPEG video WebSocket path.
- Keep `libgfortran5` and `libegl1` in the container dependencies; the ARM64 Open3D wheel requires them even without a GUI.
- Keep the DepthAI 3.12.0 pin aligned with the pinned depthai-nodes revision. The OAK4 visibility implementation has no custom native kernels; do not restore the old `build_native` step or compiler dependency.
- MeasureAnythingDetection messages stay in one host process. They have no XLink or RemoteConnection serialization. Publish native encoded frames and annotations instead.
- Keep PointCloud's explicit CAM_A RGB coordinates, millimeters, calibrated translation, identity custom transform, and organized output. Check that raw image and cloud metadata share the CAM_A reference. Do not apply the source optical pose again.
- Keep ImageAlign's target branch undistorted and separate from raw detector RGB. Its target input reuses the latest geometry and stays nonblocking. Keep the correction node's aligned and exact source-passthrough streams lossless. Do not substitute a left camera image or apply correction twice.
- The calibration cloud stays organized to 768 × 480. Detector input contains only finite, nonzero XYZ and retains its native metadata.
- Keep raw RGB and mono inputs unrectified. Do not substitute the depth backend's rectified views or resize detector inputs.
- Capture defaults to 10 FPS. Video follows matching measurement frames after plane selection. The frontend reports capture and measurement rates separately.
- Enable the IR laser dot projector at normalized intensity `1.0` when `getIrDrivers()` reports hardware. Log unsuccessful enabling without stopping the app, and skip devices without IR drivers.
- Keep native annotation metadata aligned to the displayed color frame, including its independent sequence counter. Use the delivered intrinsics, distortion, and pose for projection.
- Keep both `BenchmarkIn` sinks on the host. Count outputs and failures independently of native report cadence. `latency_samples` describes sampled cumulative capture-to-output latency, not isolated node execution time.
- Keep the camera fixed after plane selection. Recalibrate whenever the camera or support surface moves.
- Calibration attempts cannot overlap. Candidate selection carries a generation to reject stale clicks.
- Candidate IDs are frame-local. Never display them as temporal tracking IDs without the app's association step.
- Require 10 consecutive observations of a tentative tracking ID before display, live visibility, or storage scheduling. Keep tentative associations internally; never construct snapshot data for them. A missed observation resets tentative confirmation, while a confirmed track retains confirmation through its tracking grace period.
- RGB thumbnails belong to the same snapshot sequence as cloud/cuboid. Crop decoding and JPEG encoding run only in the storage worker. Fetch thumbnails by tracking ID and saved revision, without point-cloud reads or images in recurring history summaries. Old records without thumbnails remain valid.
- Preview overlays are mutually exclusive. Color depth through public `ApplyDepthColormap`, sanitize RAW16 sentinel values, and match its sequence/timestamp before blending at 50%. Support-plane preview colors only valid points within 10 mm of the selected plane. Keep explicit NV12 chroma offsets matching the SDK header before hardware encoding.
- Failed frames, no-fit results, and unknown heights are distinct outcomes. Do not replace missing dimensions with zeros.
- Keep local scene images under ignored `evidence/`.
- Keep storage serialization and I/O off the controller thread. Retain the single in-flight job and later-sequence gates, atomic replacement, 20-record retention, and durable ID high-water. Do not derive visibility from the tracker's grace-period entries.
- Keep the startup OpenCV thread budget and lazy active-plane NV12 decoding. The preview conversion uses Python OpenCV and public frame setters; its NV12 bytes must match the SDK conversion. Storage padding is outside the delivered RGB image.
- Use `measured.plane.normal` for cuboid height and width axes. The measurement plane can normalize the selected plane's sign.

## Related Examples

- [apps/box-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/box-measurement) for the static frontend, service controls, and support-plane workflow.
- [apps/onnxruntime-track-anything](https://github.com/luxonis/oak-examples/tree/main/apps/onnxruntime-track-anything) for matched H.264 video and native annotations.
- [apps/p2p-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/p2p-measurement) for frontend services and pipeline host nodes.
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d) for the unified Depth node.

## Validation

- Run `python3 -m unittest discover -s tests -v` and `npm --prefix frontend run build` in this directory.
- Run `oakctl app run .`, open the printed HTTPS frontend URL, trigger support-plane calibration, inspect previews, and select the true supporting surface.
- Confirm matching H.264 RGB and native boxes with tracking IDs and dimensions. Recalibrate and verify that measurement resumes without restarting the pipeline.
- Inspect `Color stream` and `Object annotations` with oakctl. Depth is internal. Process startup alone does not validate measurement.
- Confirm idle and active ten-second benchmark log summaries for both object stages.
- Open a saved measurement, orbit its point cloud and cuboid, update it while visible, and confirm history survives a restart. An old ID after restart must show **Object not in frame**.
- Check both overlay toggles and matching video/annotation metadata. Leave overlays and evidence capture off for throughput observations.
- Use `--evidence evidence` to save metadata, the selected plane, RGB, overlay, and structured results locally.
- Record completed live checks and their limits in the PR description. Keep local recordings and screenshots under ignored `evidence/`. Physical accuracy requires a separate reference-dimension evaluation.
