# Parcel measurement validation

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
