# AGENTS.md

## Summary

Automatically segment objects from a point cloud and measure their length, width, and height without a neural-network object detector. This OAK4 app combines support-plane calibration, RGB tracking overlays, and saved 3D measurements.

## Use This Example When

- You need automatic point-cloud object segmentation and dimensions on a user-selected horizontal support plane.
- You need RGB boxes labelled with tracking IDs and length, width, and height.
- You need to measure objects without selecting or training a neural-network object detector.
- You need a frontend app with service controls and event-driven pipeline host nodes.

## Do Not Use This Example When

- You need persistent object identity across occlusion or cameras.
- You need RVC2, click-selected object segmentation, or point-to-point measurement.
- You need guaranteed measurement accuracy without a scene-specific evaluation.

## Quick Facts

- `Category:` `apps/measure-anything`
- `Shape:` `frontend`
- `Entrypoint:` [backend/src/main.py](backend/src/main.py), pipeline lifetime, services, and topic publication
- `Pipeline:` [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py), all capture, calibration, measurement, encoding, and benchmark nodes
- `Host nodes:` [backend/src/depthai_pipeline/nodes.py](backend/src/depthai_pipeline/nodes.py), `MeasurementController` and `BenchmarkLogger`
- `Preview worker:` [backend/src/depthai_pipeline/preview.py](backend/src/depthai_pipeline/preview.py), calibrated overlay remapping and paired video/annotation output
- `Geometry:` [backend/src/depthai_pipeline/geometry.py](backend/src/depthai_pipeline/geometry.py) and [backend/src/depthai_pipeline/rendering.py](backend/src/depthai_pipeline/rendering.py)
- `Domain state:` [backend/src/measurement/domain.py](backend/src/measurement/domain.py), calibration lifecycle and tracking
- `Measurement history:` [backend/src/measurement/history.py](backend/src/measurement/history.py), durable snapshots and scheduling; [backend/src/measurement/storage_node.py](backend/src/measurement/storage_node.py), asynchronous writer; [backend/src/measurement/snapshot.py](backend/src/measurement/snapshot.py), public message extraction
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx), React and Luxonis `DepthAIContext` and `Streams`
- `Frontend hosting:` [backend/src/util/frontend_server.py](backend/src/util/frontend_server.py), built `frontend/dist` on loopback port 8082 for peripheral runs; [oakapp.toml](oakapp.toml), static build and the base image's HTTPS proxy for standalone runs
- `Mode:` host plus OAK4 standalone packaging
- `Requires:` OAK4 RGB, stereo, processed accelerometer reports, Python 3.12, and Node.js 24 for the frontend build
- `Capture:` 10 FPS, unrectified RGB 2000 × 1500 NV12 and left and right 1280 × 800 GRAY8
- `Depth:` unified `Depth.build(fps=10)` with SDK defaults, ImageAlign to an undistorted 768 × 480 RGB branch, public ImageAlignDepthCorrection, then native organized PointCloud
- `Topics:` `Color stream` as H.264 and `Object annotations` as native `ImgAnnotations`, in the `preview` group
- `Replay calibration:` [backend/src/util/replay.py](backend/src/util/replay.py), recorded device reference and PointCloud calibration
- `Dependencies:` [backend/requirements.txt](backend/requirements.txt), immutable depthai-nodes PR 348 revision with `measure-anything` and `box-measurement` extras

## Read First

- [backend/src/depthai_pipeline/init_pipeline.py](backend/src/depthai_pipeline/init_pipeline.py) for public node wiring and stream configuration.
- [backend/src/depthai_pipeline/nodes.py](backend/src/depthai_pipeline/nodes.py) for event handling, service commands, scene admission, and result joins.
- [backend/src/depthai_pipeline/rendering.py](backend/src/depthai_pipeline/rendering.py) and [backend/src/depthai_pipeline/geometry.py](backend/src/depthai_pipeline/geometry.py) for frame metadata, previews, and native annotations.
- [frontend/src/services.ts](frontend/src/services.ts) for the shared frontend service contract.
- [oakapp.toml](oakapp.toml) for the static frontend build and runtime dependencies.
- [README.md](README.md) for operation and scene requirements.

## Architecture

One device-backed pipeline creates every node before startup. Detector images retain the unrectified grids and native metadata. A separate RGB output is undistorted and stretched to 768 × 480 for ImageAlign's target geometry. The unified `Depth` node is built with only the FPS argument and supplies native depth to ImageAlign. Keep algorithm, model, and source resolution at SDK defaults; log the resolved algorithm/configuration in the capture profile. The public `ImageAlignDepthCorrection` consumes `outputAligned` and the same node's exact `passthroughInput` with policy `source_axial_requires_correction`. Its corrected target-axial RAW16 output feeds PointCloud. Host Sync retains the matching structured correction result alongside corrected depth, native organized cloud, and raw images.

`read_scene` validates the depth, cloud, and correction frame identity. It zeros rows for invalid RAW16 depth or nonfinite XYZ, preserving organized layout. The controller's `calibration_cloud` output supplies that sanitized organized cloud to SupportPlaneCalibrator. The detector receives its finite nonzero rows. Correction provenance travels with SceneFrame, state, startup logs, and saved measurement details.

`MeasurementController` is a `ThreadedHostNode`. Its blocking `MessageQueue.getAny` dispatches scene, IMU, calibration, detection, measurement, and command inputs. Service callbacks enqueue commands or read locked state snapshots. `backend/src/main.py` manages frontend hosting, pipeline tasks, remote key input, and shutdown. It does not poll application data queues.

`SupportPlaneCalibrator` receives the organized native cloud. The controller rotates processed accelerometer specific force from RGB optical axes into the common reference, without negation. Calibration candidates retain a generation so stale selections can be rejected. Every five seconds, the controller sends public `SupportPlaneCalibrationControl.verify` and consumes `verificationOutput`. Only one verification is pending. Generation, plane, and source sequence guard stale replies. Rejection expires the selected plane, stops admission, invalidates pending previews/results, and prompts recalibration in the frontend.

The detector builds without a support plane. The controller admits object scenes after selection and sends `MeasureAnythingDetectorConfig` immediately before the first scene. Later selections use the same config input. At most two scenes remain in flight to absorb timing jitter, retaining RGB until detection and measurement results join by cloud sequence. Recalibration keeps old jobs in those slots until they complete, then rejects their results. Sequence regression cannot rewind tracking or video. This measurement bound is separate from the single in-flight storage job.

The controller sends preview jobs to `PreviewRendererNode`, whose size-one nonblocking queue keeps the latest waiting frame. The worker emits paired native NV12 RGB and `ImgAnnotations`, retaining the color sequence, timestamps, and transformation. It drops stale-generation work before and after rendering. RGB decoding is lazy; normal RGB preview passes the original NV12 frame directly to the H.264 encoder. Candidate previews are separate JPEG still images, fetched once per candidate generation. Depth stays internal.

`BenchmarkLogger` is a host node with a timed blocking wait. It counts actual detector and dimensioner outputs and consumes the two host `BenchmarkIn` report streams. It emits ten-second DEBUG summaries even while the detector waits for its first plane. Successful support-plane verification details also use DEBUG; rejected verification remains a warning. Enable these diagnostics with `--log-level DEBUG`.

The React frontend uses the same Luxonis viewer, service hooks, static build pattern, and shared `AppShell` as the other apps. Keep `AppShell.tsx` and the shared `index.css` synchronized with `custom-frontend/raw-stream`; app-specific layout lives in `App.css`. Processing and tab navigation stay outside the scrolling panel content. Failed-frame explanations use `frame.failure_code` and `frame.message` in a fixed-height area shared with the healthy-frame help text. Healthy or idle frames clear the failure code. Never restore ordinary detection-count text above the tabs. `getMeasurementState` returns state without preview images. `calibrateSupportPlane` starts calibration, `selectSupportPlane` accepts `{generation, index}`, and `getSupportPlanePreview` accepts the same candidate key and returns `{jpeg}`. Standalone mode uses the base image to serve the compiled frontend and proxy `/dai` to `RemoteConnection`. Peripheral mode serves `frontend/dist` through `FrontendServer` on loopback port 8082 and logs a URL with a `ws_url` query parameter targeting the RemoteConnection port, 8765 by default. The frontend must use that parameter when present; keep the packaged `/dai` connection as its default.

`MeasurementStore` uses SQLite in `OAKAGENT_STORAGE_APP` or the example-root ignored `data/` directory. Moving the backend must not change the peripheral default database location. Startup loads at most 20 summaries and the tracking ID high-water mark. `SaveScheduler` owns saved, waiting, update-requested, and busy state. The controller sends one immutable segmented-cloud reference and small metadata through `history_jobs`. `StorageHostNode` performs encoding and the transaction, then acknowledges success or failure. No further snapshot is submitted until acknowledgement, and no sequence can submit twice. Waiting IDs keep their first-seen order; evicted IDs remain marked saved for the current run.

`getMeasurements` returns cached summaries, current observations, and active-track state. `getMeasurement` reads a single detail record on the service thread. `requestMeasurementUpdate` accepts `{track_id}` while its confirmed track is retained and schedules a later measured observation. Temporary loss preserves pending updates until reacquisition or track removal. SQLite replaces the previous cloud and metadata atomically. New tracks after restart use fresh IDs rather than overwriting historical records.

`setPreviewOptions` accepts `{depth, support_plane}` booleans. The preview worker caches the calibrated raw-RGB-to-undistorted-depth remap by full delivered geometry. It requires a shared RGB optical center, selects either the public colormap output or the plane-only texture on the depth grid, and uses OpenCV remapping and masked blending. Do not restore per-frame full-cloud reprojection or raw depth resizing. The Measurements modal uses Three.js to display the cloud and cuboid in the same transformed coordinate frame.

## Constraints

- Import only names exported by `depthai_nodes.node` and `depthai_nodes.message` at runtime. Do not import frozen algorithms or node implementation internals.
- Standalone packaging uses the Quay `oakapp-base` image and Python 3.12. Keep `/entrypoint.sh` and the `static_frontend` build so the base image serves the frontend.
- Keep `libgfortran5` and `libegl1` in the container dependencies; the ARM64 Open3D wheel requires them even without a GUI.
- Keep the DepthAI pin aligned with the pinned depthai-nodes revision. The commit pin is for development; switch to a compatible released depthai-nodes version before merging this example.
- MeasureAnythingDetection messages stay in one host process. They have no XLink or RemoteConnection serialization. Publish native encoded frames and annotations instead.
- Keep PointCloud's explicit CAM_A RGB coordinates, millimeters, calibrated translation, identity custom transform, and organized output. Check that raw image and cloud metadata share the CAM_A reference. Do not apply the source optical pose again.
- Keep ImageAlign's target branch undistorted and separate from raw detector RGB. Its target input reuses the latest geometry and stays nonblocking. Keep the correction node's aligned and exact source-passthrough streams lossless. Do not substitute a left camera image or apply correction twice.
- Stereo replay can deliver NV12 despite a GRAY8 request. `mono_frame` in `rendering.py` extracts exact active luma while preserving frame identity and calibration. Native GRAY8 and RAW8 pass through unchanged.
- Holistic replay binds PointCloud to the recording's camera ID and calibration through `util/replay.py`. Do not substitute the attached device's calibration or rewrite recorded frame metadata. Bound validation to the first loop because replay timestamps can drift independently across sources.
- The calibration cloud stays organized to 768 × 480. Detector input contains only finite, nonzero XYZ and retains its native metadata.
- Keep raw RGB and mono inputs unrectified. Do not substitute the depth backend's rectified views or resize detector inputs.
- Capture defaults to 10 FPS. Video follows matching measurement frames after plane selection. The frontend reports capture and measurement rates separately.
- Enable the IR laser dot projector at normalized intensity `1.0` when `getIrDrivers()` reports hardware. Log unsuccessful enabling without stopping the app, and skip devices without IR drivers.
- Keep native annotation metadata aligned to the displayed color frame, including its independent sequence counter. Use the delivered intrinsics, distortion, and pose for projection.
- Keep both `BenchmarkIn` sinks on the host. Count outputs and failures independently of native report cadence. `latency_samples` describes sampled cumulative capture-to-output latency, not isolated node execution time.
- Works best with larger, separated, box-like objects in good lighting on a flat support surface. Point-cloud segmentation does not require a neural object detector, but the SDK default depth backend can use neural inference.
- Keep the camera fixed after plane selection. Recalibrate whenever the camera or support surface moves.
- Calibration attempts cannot overlap. Candidate selection carries a generation to reject stale clicks.
- Candidate IDs are frame-local. Never display them as temporal tracking IDs without the app's association step.
- Require 10 consecutive observations of a tentative tracking ID before display, live visibility, or storage scheduling. Keep tentative associations internally; never construct snapshot data for them. A missed observation resets tentative confirmation, while a confirmed track retains confirmation through its tracking grace period.
- RGB thumbnails belong to the same snapshot sequence as cloud/cuboid. Crop decoding and JPEG encoding run only in the storage worker. Fetch thumbnails by tracking ID and saved revision, without point-cloud reads or images in recurring history summaries. Old records without thumbnails remain valid.
- Preview overlays are mutually exclusive. Color depth through public `ApplyDepthColormap`, sanitize RAW16 sentinel values, and match its sequence/timestamp before blending at 50%. Support-plane preview colors only valid points within 10 mm of the selected plane. Keep explicit NV12 chroma offsets matching the SDK header before hardware encoding.
- Failed frames, no-fit results, and unknown heights are distinct outcomes. Do not replace missing dimensions with zeros.
- Keep local scene images under ignored `evidence/`.
- Keep storage serialization and I/O off the controller thread. Retain the single in-flight job and later-sequence gates, atomic replacement, 20-record retention, and durable ID high-water. Do not derive visibility from the tracker's grace-period entries. Keep `in_frame` tied to observed objects and publish `track_active` separately for confirmed, retained tracks. Use track lifetime for update availability and pending-update retention. Only removed tracks show Object not in frame; expiry must also run without new measurement results. Track removal cancels pending requests without releasing an in-flight writer or creating a global storage error. Initial-save errors retry automatically after a one-second monotonic cooldown while the track is retained. Check `SaveScheduler.needs_snapshot` before constructing snapshot data and again during selection. Saved-record update errors still require an explicit update request.
- Keep the startup OpenCV thread budget and lazy active-plane NV12 decoding. The preview conversion uses Python OpenCV and public frame setters; its NV12 bytes must match the SDK conversion. Storage padding is outside the delivered RGB image.
- Use `measured.plane.normal` for cuboid height and width axes. The measurement plane can normalize the selected plane's sign.
- Keep Processing outside the scrollable tab panels. Overlay controls belong to Configuration. Camera-to-cuboid-center distance is computed in the frontend from saved CAM_A coordinates as the norm of `base_center_mm + up_axis * height_mm / 2`; it requires no pipeline output or storage change.

## Related Examples

- [apps/box-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/box-measurement) for the static frontend, service controls, and support-plane workflow.
- [apps/onnxruntime-track-anything](https://github.com/luxonis/oak-examples/tree/main/apps/onnxruntime-track-anything) for matched H.264 video and native annotations.
- [apps/p2p-measurement](https://github.com/luxonis/oak-examples/tree/main/apps/p2p-measurement) for frontend services and pipeline host nodes.
- [apps/object-volume-measurement-3d](https://github.com/luxonis/oak-examples/tree/main/apps/object-volume-measurement-3d) for the unified Depth node.

## Validation

- Install `backend/requirements.txt` in an isolated environment. Run `python3 -m unittest discover -s tests -v`, `npm --prefix frontend run build`, and `npm --prefix frontend run lint` in this directory.
- Run `oakctl run-script .venv/bin/python backend/src/main.py --device <OAK4-IP>`, open the logged loopback frontend URL, and verify video, service discovery, calibration, and saved measurement access. Use `--frontend-port` to select another HTTP port. The compiled `frontend/dist` must exist first.
- Run `oakctl app run .`, open the printed HTTPS frontend URL, trigger support-plane calibration, inspect previews, and select the true supporting surface.
- Confirm matching H.264 RGB and native boxes with tracking IDs and dimensions. Recalibrate and verify that measurement resumes without restarting the pipeline.
- Inspect `Color stream` and `Object annotations` with oakctl. Depth is internal. Process startup alone does not validate measurement.
- Confirm INFO logs remain quiet during normal measurement. With `--log-level DEBUG`, confirm idle and active ten-second benchmark summaries for both object stages and successful plane verification details. A rejected plane must still warn at INFO configuration.
- Open a saved measurement, orbit its point cloud and cuboid, update it while visible, and confirm history survives a restart. An old ID after restart must show **Object not in frame**.
- Check both overlay toggles and matching video/annotation metadata. Leave overlays and evidence capture off for throughput observations.
- Use `--evidence evidence` to save metadata, the selected plane, RGB, overlay, and structured results locally.
- Replay a matching holistic recording by setting `DEPTHAI_REPLAY` to its `.tar` path on the backend process. The recording must contain CAM_A, CAM_B, CAM_C, IMU, and calibration. Check a decoded source frame and real measurement outputs; startup alone does not prove replay. Use a separate `--storage` database for repeatable replay checks.
- Record completed live checks and their limits in the PR description. Keep local recordings and screenshots under ignored `evidence/`. Physical accuracy requires a separate reference-dimension evaluation.
