# Parcel measurement validation

## RGB thumbnails, corrected overlays, and plane verification, 2026-11-25

Saved measurements now include an RGB crop from the same source frame. Crop decoding and JPEG encoding run only in the storage worker; history polls carry availability rather than image bytes. Chrome loaded the thumbnails and updated the current object's cloud, cuboid, and crop together through **Update Measurement**. The stored revision advanced from 1 to 2, the source sequence advanced, and the JPEG changed. All 20 saved previews survived an app restart byte-for-byte. Earlier records without previews remain supported.

The green/magenta video corruption came from missing NV12 chroma offsets. Host decoding silently inferred the offsets, so earlier byte/decode tests missed the invalid frame header. The fix matches the SDK's explicit Y/UV layout. Regression tests compare public frame headers, bytes, and literal-offset decoding with padded 2000 × 1500 camera layouts. Live H.264 video in Chrome now shows the public `ApplyDepthColormap` output blended at 50%, with invalid depth transparent. The mutually exclusive support-plane mode highlights only visible plane inliers; parcels and background retain their RGB colors. Earlier overlay checks below established throughput but missed this encoding defect.

The public calibrator verifies the selected plane every five seconds. The normal final run logged 28 accepted checks without errors in the collected interval. A temporary local test build displaced the selected plane by 500 mm and passed it through the same public verification path. The calibrator rejected it, measurement admission stopped, and Chrome switched from Measurements to Calibration with the recalibration warning. The final deployed build contains no test service. Unit checks also cover stale verification replies, queued result rejection, and generation changes. Switching away from Measurements unmounts its detail modal so it cannot obscure the warning.

Tentative tracking IDs require 10 consecutive observations before boxes, live visibility, or snapshot scheduling. Tests verify no display or snapshot construction for observations 1–9, confirmation and saving on observation 10, reset after a missing tentative observation, and confirmation retention during the existing tracking grace period. The current live parcel confirmed and saved; short-lived clutter tracks did not enter the new history.

With the final packaged app, Chrome connected, and evidence capture disabled, three ten-second windows per mode followed two-second warmups. A live snapshot update occurred during this check. Actual received H.264 rates were:

| Mode            | Median FPS |  Window range |
| --------------- | ---------: | ------------: |
| RGB             |      9.993 |   9.993–9.997 |
| Colorized depth |     10.002 |  9.987–10.013 |
| Support plane   |     10.018 | 10.001–10.042 |

All 900 annotation frames contained the confirmed parcel and complete dimension labels. There were no stream errors or warnings; the collected detector/dimensioner benchmark windows reported approximately 10 FPS and zero failed batches. This scene had one confirmed object, so this update does not establish a new three-object performance result. The earlier three-object measurements below remain historical evidence. Physical dimension accuracy remains unvalidated.

All 70 backend tests, frontend type checking/build, Biome, repository hooks, agent-document checks, and generated-index checks pass. Private screenshots and test metadata remain under ignored `evidence/history-2026-11-25/`. The final app was left running with overlays and evidence capture disabled.

## Measurement history, RGB depth correction, and performance, 2026-11-25

The example adds persistent history for the latest 20 saved tracking IDs, an interactive segmented-cloud and cuboid viewer, explicit snapshot replacement, labeled L/W/H annotations, and optional depth and support-plane overlays. SQLite storage runs in one host node. Its scheduler submits one object per sequence and waits for acknowledgement before submitting another. It retains waiting order across frames and does not automatically resave objects whose records were evicted.

Live service checks compared all 20 detail records before and after an app restart, including their point bytes and cuboid metadata. Every record survived unchanged. Historical tracks became unavailable for live updates, and new IDs continued above the persisted high-water mark. Explicit updates through both the service and frontend button advanced the source sequence and stored revision. Browser checks covered the Measurements tab, modal, orbit/zoom/reset controls, unavailable-object status, and both overlays. Local evidence is under ignored `evidence/history-2026-11-25/`.

The depth path is NeuralDepth → ImageAlign → public ImageAlignDepthCorrection → native PointCloud. Alignment uses a separate undistorted 768 × 480 RGB branch, while detector RGB and mono images retain their raw grids. Correction uses the exact ImageAlign depth passthrough and explicit source-axial policy. The live node reported `source_axial_to_target_axial/1` and `target_camera_axial_z` with matching source associations. Corrected depth, organized cloud, and provenance identities are checked at runtime; invalid depth rows are zeroed before calibration. Saved measurements include the correction provenance. The installed upstream host fixture also passed its geometry assertions with the pinned SDK and dependency.

Performance work removed full-cloud reprojection from the preview, cached the calibrated remap, made RGB decoding lazy, and moved paired preview output into a separate host node. Two bounded measurement slots absorb capture jitter. Python OpenCV uses one worker thread; active-plane NV12 conversion avoids additional conversion pools. Tests compare the produced NV12 bytes with the SDK and cover padded rows, row stride, and non-row-aligned chroma offsets.

The operator placed three objects on the support surface. With evidence capture disabled and the standard Chrome frontend connected, five ten-second windows per mode followed two-second warmups. The collector decoded native packet metadata, counted received video and annotations, and discarded image payloads. Camera-device timestamps yielded approximately 10.00 delivered video FPS in every mode. Arrival-time measurements varied with packet timing:

| Preview       | Median video FPS | Arrival-time FPS range |
| ------------- | ---------------: | ---------------------: |
| RGB           |            10.02 |             9.99–10.03 |
| Depth         |            10.02 |             9.96–10.07 |
| Support plane |            10.03 |             9.96–10.10 |
| Both overlays |             9.99 |             9.95–10.04 |

Across 2,000 timed annotation frames, none were empty and all contained complete dimension labels. Exactly three complete labels appeared in 1,687 frames. The detector sometimes merged objects or included background clutter, yielding one to five labels; this is not a detector-recall or accuracy claim. There were no stream decoding errors, timestamp conflicts, or missing source sequences within the video windows. The native detector and dimensioner logs reported 9.9–10.1 output batches per second over ten-second windows, with zero failed batches. Small excursions above 10 reflect window boundaries and receive timing, not a higher configured capture rate.

After switching the final decoder to exact active Y/UV views, another live combined-overlay window confirmed the same throughput. All 53 backend tests, frontend type checking, production build, Biome, repository hooks, agent-document checks, and generated-index checks pass. The tests include blocked-writer behavior, atomic rollback, retention, explicit-update races, fair scheduling, two-scene admission, stale-generation rejection, calibrated remapping, and paired preview output. Physical dimension accuracy and holistic replay remain unvalidated.

## Dependency update, 2026-11-25

The example now pins depthai-nodes PR 348 revision `61dd0b863e055aaf3fd0d9ac2b9e92247cfbf188`, using `algorithm-5e4abc3a09b54148950317cdeac60ba2`. The detector, dimensioner, calibration, plane, and config interfaces used by the app are unchanged. The replacement implementation removes the old custom native kernels, so the obsolete compiler dependency and kernel-build command were removed. The DepthAI pin is now 3.12.0 to satisfy the dependency's exact SDK requirement.

All 17 app tests pass in a fresh environment with these pins, and the installed dependency check passes. The packaged app also built and ran on the connected OAK4. Runtime package metadata confirmed the exact dependency commit and SDK version, and successful measurements carried the new algorithm identity. Support-plane calibration, selection, and a second selection worked in one running pipeline. The returned measurement plane matched the selected plane after sign normalization. Native video and annotation topics and idle and active benchmark logs remained available. Local evidence is under ignored `evidence/dependency-2026-11-25/`.

The upstream synthetic example constructs and runs both public parcel nodes and returns a measured parcel, but its dimension-tolerance assertion fails with the replacement baseline. Its length is 213.6 mm against an expected 220 mm with a 5 mm tolerance. It is not counted as a passing test. A sanitized reproduction was submitted through the authorized Luxonis feedback tool. No physical reference dimensions were compared; accuracy and replay remain unvalidated for this update. Earlier sections describe previous dependency revisions and algorithms.

## Standard frontend and host-node update, 2026-11-23

The current app uses the repository's React/Vite frontend, Luxonis `DepthAIContext` and `Streams`, static frontend packaging, and the base image's `/entrypoint.sh`. It has no bespoke Python frontend server or JPEG video WebSocket. The user's `g++` dependency and bundled parcel native-kernel build step remain in the container configuration.

The main loop only handles pipeline lifetime and remote keys. `ParcelController` handles native scene, IMU, calibration, parcel-result, and service-command events through blocking `MessageQueue.getAny`. `BenchmarkLogger` handles the actual output and native benchmark report streams, with a timed blocking wait for ten-second logging. All nodes are created upfront in one device-backed pipeline.

The package built successfully on the OAK4, including the Node.js 24 frontend build. The running app printed its actual frontend address, `https://<OAK4-IP>:9000`; oakctl supplied port 9000 through `OAKAPP_STATIC_FRONTEND_PORT`. The base image defaults to 8000 when that variable is absent. The LAN test was explicitly authorized, and the operator handled the device certificate warning in Chrome.

Live browser checks confirmed 2000 × 1500 H.264 RGB, support-plane calibration, candidate previews, explicit candidate confirmation, native parcel boxes with tracking IDs and dimensions, and recalibration without restarting capture. Both selections returned successful measurement batches. The second measurement plane matched the selected plane after sign normalization, and the run logged one pipeline start. Idle and active ten-second reports from both benchmark stages were checked. These are functional checks, not a measurement accuracy or algorithm speed comparison.

RemoteConnection inspection advertised exactly `Color stream` as an `EncodedFrame` and `Parcel annotations` as `ImageAnnotations`. The depth topic was removed; depth remains internal. `oakctl inspect frames` identified `AVC/H264` but cannot decode that encoding, so browser screenshots provide the visual evidence. Native messages were dumped and checked for normalized boxes, tracking and dimension labels, and 2000 × 1500 metadata. Paired video and annotation messages had identical sequence counters, timestamps, and transformations. The inspector limitation was reported to Luxonis.

All 17 backend tests pass. They include native annotation identity and empty-overlay behavior, service commands handled by a running pipeline node, stale selections, and invalid identifiers. TypeScript checking, the Vite production build, Biome, Python checks, agent-document validation, and the generated index check pass. Review also caught a missing frontend frame-status field; it was restored so failed-frame and no-eligible-parcel messages remain visible.

Local screenshots, native messages, and benchmark records are under ignored `evidence/native-frontend/`. The test copy only adds evidence saving to the entrypoint. Physical dimension accuracy and holistic replay remain unvalidated. Earlier sections describe the previous frontend and transport.

## Single-pipeline API update, 2026-11-23

The example now pins depthai-nodes PR 348 revision `f000977fbcf9238b1441277d2d0202e30d758ab0`. One device-backed pipeline creates all camera, calibration, detector, and dimensioner nodes and their queues before starting. The detector builds without an initial plane. The first selected plane and later selections arrive through `ParcelDetectorConfig` on `inputConfig`, immediately before the next admitted scene.

A native synthetic check using the app's `SceneSource` fed a scene before calibration and observed no detection or measurement output. Sending the first plane activated measurements. A later config changed the measurement plane in the same running graph. Independent image counters and native timestamps were retained.

The packaged app built and ran on the connected OAK4. Before selection, its frontend returned live 2000 × 1500 RGB, an idle calibration state, and no parcel results. Two calibration attempts produced floor candidates whose previews were opened and checked. Selecting each floor candidate returned successful measured parcel batches with tracking IDs and dimensions. Each measurement plane matched the corresponding selected plane after sign normalization. The run logged one pipeline start; calibration and selection did not recreate nodes or restart capture. The generated RGB overlay was opened and checked.

All thirteen behavior, geometry, and benchmark-window tests, Python compilation, agent-document validation, the index check, and diff checks pass. An independent review found no actionable defects in config ordering or frame/generation association.

The hardware test used a temporary copy bound to loopback with evidence saving enabled. Its Python sources matched the example. Test output and images are under ignored `evidence/single-pipeline/`, including `native-config-check.json` and `live-config-check.json`. The test app was stopped afterward. Physical dimension accuracy, holistic replay, and standalone LAN frontend access were not validated by this run.

## Ten-second benchmark logs, 2026-11-23

Two host `BenchmarkIn` nodes receive the detector and dimensioner outputs in the same pipeline. The app collects native latency reports and prints a separate `parcel_benchmark` JSON summary for each stage every ten seconds. Output batch counts, failed batches, output FPS, latency sample counts, and mean source-to-output latency are logged. The latency includes capture, queues, and upstream processing; it does not isolate the execution time of either node.

DepthAI 3.12.2 emits a benchmark report on the input after the configured sample count. A native check with `sendReportEveryNMessages(1)` observed one report after two outputs, reporting one latency sample. Throughput therefore counts actual stage outputs rather than summing native report counts. Native reports supply only the sampled latency. The SDK behavior was reported to Luxonis.

The benchmark-enabled packaged app was tested on the OAK4 with loopback access. Before calibration, both stage logs reported zero output FPS and no latency. After selecting the floor, both stages returned successful parcel results and emitted active ten-second summaries with nonzero output and latency sample counts. These checks establish instrumentation behavior in one live run, not a comparison of algorithm speed or a measurement accuracy claim. Four deterministic tests cover timed reporting, weighted latency, independent output counts, failure counts, idle windows, and reset behavior.

## Earlier API update, 2026-11-23

The previous example pinned depthai-nodes PR 348 revision `6f6cad59a5e1169f56d2c2b74da7aed5ca6f1b60`. Its parcel API and algorithm code are identical to revision `168701d7a4472dfb880adcf6d06b52f7c3a5c6bd`, used for these earlier live checks. The later revision adds an algorithm visualization HTML file.

The connected OAK4-D R9 was tested with DepthAI 3.12.2, Python 3.12, Open3D 0.20.0, and the parcel extra's pinned numerical dependencies.

| Source      | Delivered grid             | Configuration                                       |
| ----------- | -------------------------- | --------------------------------------------------- |
| RGB         | 2000 × 1500                | NV12, unrectified, 10 FPS                           |
| Left        | 1280 × 800                 | GRAY8, unrectified, 10 FPS                          |
| Right       | 1280 × 800                 | GRAY8, unrectified, 10 FPS                          |
| Depth       | 768 × 480                  | NeuralDepth LARGE                                   |
| Point cloud | 768 × 480 organized points | Native PointCloud, DEFAULT coordinates, millimeters |

The live metadata contains the delivered intrinsics, distortion, and common CAM_A reference. The raw camera images retain distortion coefficients. The cloud retains its native transformation metadata and independent sequence counter. The source timing and frontend report approximately 10 FPS capture.

The browser calibration control produced plane candidates with previews projected into the raw RGB image. Selecting a candidate started the parcel nodes with that actual plane. A second live calibration and selection exercised `ParcelDetectorConfig` without rebuilding the detector. The saved measurement plane matched each selected plane after the node's documented sign normalization. Both attempts returned successful frame outcomes.

The updated nodes produced measured objects, RGB boxes, tracking IDs, and dimensions. Parcel detections remained intermittent, and clutter was also returned as eligible. Three 2000 × 1500 inspection frames were opened; that sample showed the parcel partly occluded and no eligible detection. A separate fifteen-second frontend sample contained 23 result snapshots, eight with measured outputs and no frame-failure messages. Those counts include native clutter detections and do not establish parcel recall.

The frontend separates configured capture FPS, observed source FPS, and measurement output rate. Capture was approximately 10 FPS. Measurement throughput was substantially lower, roughly 1–1.5 FPS in the sampled run with the PR's documented optional native kernels. A fallback run was also functional. The optional kernels were built only in the temporary test environment, with no algorithm source changes or private runtime imports in the app. These are observations from a live scene on a busy host, not a controlled speedup comparison or a 10 FPS measurement guarantee.

Local artifacts are ignored by Git under `evidence/update-2026-11-23-final/`. They include delivered metadata, the selected plane, `config-update-check.json`, both calibration attempts, temporal results, RGB, and inspection frames. Earlier update and native-run directories retain the other local checks.

## Automated checks

All nine behavior and geometry tests pass. They cover calibration lifecycle and stale selection, tracking association, delivered distortion and camera poses, bounds on the actual RGB grid, invisible points, and IMU reference rotation. The current upstream synthetic parcel example also passes using both fallback and optional native kernels.

An import audit confirms every depthai-nodes import in the application and tests is exported through `depthai_nodes.node` or `depthai_nodes.message`. Independent review found no confirmed code defects. Its requested live config-update check was then completed.

These commands pass from the repository root.

```bash
python3 -m unittest discover -s apps/parcel-measurement/tests -v
node --check apps/parcel-measurement/frontend/app.js
python3 -m compileall -q apps/parcel-measurement
python3 scripts/validate_agents_docs.py
python3 scripts/generate_agents_index.py --check
git diff --check
```

## Scope and earlier checks

Physical dimension accuracy was not compared against a reference, as requested. Holistic replay and standalone LAN frontend access remain untested. Host services bind to localhost by default.

The original November 20 implementation was tested with a different 640 × 400 capture profile and the previous public API. Those historical artifacts remain under `evidence/live/` and `evidence/final/`; they do not validate the current source profile or API.

## Standalone runtime repair, 2026-11-23

The reported `oakctl app run .` failure was reproduced with the original configuration. It selected bare Debian and failed with `/bin/sh: 1: python3: not found`.

The corrected configuration selects `luxonis/oakapp-base:1.3.0`, installs and starts with Python 3.12, and includes the `libgfortran5` and `libegl1` libraries required by the ARM64 Open3D wheel. The application starts directly, without the vendor reverse proxy or WebRTC services.

The container build completed on the OAK4. The app logged `Pipeline started.` and its frontend WebSocket returned a live 2000 × 1500 RGB frame. Container imports reported Python 3.12.11, DepthAI 3.12.2, and Open3D 0.20.0. The structured source profile matched the requested camera grids and 10 FPS setting. The saved frame was opened and checked.

Verification used a temporary copy with `--host 127.0.0.1` so frontend and inspection services stayed on the device's loopback interface. That was the only runtime configuration difference. Live output was read using `oakctl app exec` inside the container. LAN exposure was not tested. The test app was stopped afterward. Artifacts remain under ignored `evidence/standalone-runtime-fix/`.
