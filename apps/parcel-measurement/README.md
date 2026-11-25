# Measure parcels with an OAK4

This example shows RGB parcel boxes, temporary tracking IDs, and length × width × height in millimeters. The frontend starts support-plane calibration and lets you select a candidate surface.

The app uses public `ParcelDetector`, `ParcelDimensioner`, and `SupportPlaneCalibrator` nodes from the pinned revision of [depthai-nodes PR 348](https://github.com/luxonis/depthai-nodes/pull/348). Capture defaults to 10 FPS with unrectified RGB at 2000 × 1500, unrectified left and right images at 1280 × 800, and NeuralDepth LARGE at 768 × 480.

## Run as an OAK App

Use an OAK4 with RGB, stereo, and an IMU. From this directory, run the packaged app.

```bash
oakctl app run .
```

Open the `Parcel frontend at https://<OAK4-IP>:<port>` address printed in the app logs from a computer on the same network. `OAKAPP_STATIC_FRONTEND_PORT` controls the port. The base image defaults to 8000; oakctl can assign another port, such as 9000.

The container builds the React frontend and serves its static files through the base image's `/entrypoint.sh` and HTTPS proxy. `RemoteConnection` supplies the video topics and control services. The app does not start a separate Python frontend server.

The container uses `luxonis/oakapp-base:1.3.0` and Python 3.12. The pinned depthai-nodes revision requires DepthAI 3.12.0 and uses the OAK4 visibility baseline. It has no custom native-kernel build step.

## Calibrate and measure parcels

1. Keep the camera fixed and show the horizontal surface supporting the parcels.
2. Click **Find support planes**.
3. Inspect the candidate previews. Green pixels mark projected plane inliers. Select the supporting table or floor rather than a parcel top.
4. Click **Use this support plane**.
5. Keep parcels separated and fully in view. Eligible parcels receive boxes with tracking IDs and dimensions.

Recalibrate after moving the camera or changing the support surface. Unknown heights appear as `?`. Failed frames show a failure reason instead of fabricated dimensions.

RGB reaches the frontend as H.264, with native annotations for boxes and labels. The app pairs each measured result with its source RGB frame before encoding. During measurement, the displayed video follows measurement throughput. Before calibration, it shows the live capture stream.

The frontend distinguishes capture FPS from measurement throughput. Capture defaults to 10 FPS. Detection and measurement use the CPU of the machine running the backend, including the OAK4 CPU in standalone mode. Their rate depends on the scene and CPU.

The logs print a `parcel_benchmark` JSON report for `ParcelDetector` and `ParcelDimensioner` every ten seconds. FPS counts actual output batches, including failures. `failed_messages` counts failed batches, and `latency_samples` counts native benchmark samples. `source_to_output_latency_ms` averages capture-to-stage latency, including queues and upstream processing. Idle windows report zero FPS and no latency.

## Run on your computer

Use Python 3.12 and Node.js 24. Install the backend dependencies in an isolated environment and start the backend.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
oakctl run-script .venv/bin/python main.py --device <OAK4-IP>
```

In another terminal, start the standard Vite development server.

```bash
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite. The backend binds to loopback by default. The packaged OAK App binds its remote connection to the device interfaces.

## Inspect and save evidence

Start the backend with `--evidence evidence` to save delivered metadata, the selected plane, RGB, an annotated image, and structured results locally.

```bash
oakctl run-script .venv/bin/python main.py --device <OAK4-IP> --evidence evidence
oakctl inspect topics
```

The published topics are **Color stream** and **Parcel annotations**. Depth remains inside the measurement pipeline. The frontend reads calibration state and rates through `getParcelState`. Candidate previews are still JPEG images requested through `getSupportPlanePreview`; they are separate from the H.264 RGB stream.

## Geometry and tracking

NeuralDepth receives the raw mono outputs. Native PointCloud produces an organized 768 × 480 cloud with DEFAULT coordinates, millimeters, calibrated translation, and an identity custom transform. The app preserves native metadata when filtering detector input points.

One pipeline creates all nodes before startup. Host nodes handle scene admission, IMU conversion, calibration results, parcel results, and timed benchmark logging. The main loop manages pipeline lifetime. The first selected plane and later selections reach the detector through `ParcelDetectorConfig` before the next admitted scene.

Raw images and the cloud retain their independent sequence counters and timestamps. Boxes project through the delivered RGB intrinsics, distortion, and pose. Video and annotations carry matching RGB metadata.

Tracking belongs to this app. The node's candidate IDs are frame-local. The app associates centers and box overlap, expires tracks after two seconds, and clears associations after recalibration. IDs can change after occlusion or fast motion.

The detector can miss parcels or classify background clutter as eligible. Use an uncluttered measurement area. This example does not claim metrology accuracy or persistent identity.

## Check the app logic

```bash
python3 -m unittest discover -s tests -v
npm --prefix frontend run build
```

See the [validation record](VALIDATION.md) for completed checks and their limits.
