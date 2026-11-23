# Parcel measurement validation

## Current API update, 2026-11-23

The example is pinned to depthai-nodes PR 348 revision `6f6cad59a5e1169f56d2c2b74da7aed5ca6f1b60`. Its parcel API and algorithm code are identical to revision `168701d7a4472dfb880adcf6d06b52f7c3a5c6bd`, used for the live checks. The later revision adds an algorithm visualization HTML file.

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
