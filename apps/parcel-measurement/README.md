# Measure parcels with an OAK4

This example shows RGB parcel boxes labeled with tracking IDs and `L: value x W: value x H: value` in millimeters. The frontend starts support-plane calibration, lets you select a candidate surface, and retains the latest 20 saved object measurements.

The app uses public `ParcelDetector`, `ParcelDimensioner`, and `SupportPlaneCalibrator` nodes from the pinned revision of [depthai-nodes PR 348](https://github.com/luxonis/depthai-nodes/pull/348). Capture defaults to 10 FPS with unrectified RGB at 2000 × 1500, unrectified left and right images at 1280 × 800, and NeuralDepth LARGE at 768 × 480.

NeuralDepth feeds `ImageAlign`, which targets a separate undistorted 768 × 480 RGB branch. Public `ImageAlignDepthCorrection` then converts aligned source-camera Z values into RGB-camera Z before PointCloud generation. The raw detector images retain their original grids.

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

## Inspect saved measurements

Open the **Measurements** tab and select an object using its RGB thumbnail and tracking ID. The thumbnail comes from the same frame as its saved measurement. The detail modal shows the segmented object point cloud, fitted cuboid, source sequence, capture time, algorithm, and support-plane metadata. Drag to orbit, right-drag to pan, scroll to zoom, or click **Reset view**.

An object must appear in 10 consecutive processed frames before its box appears or its measurement is saved. A missing observation resets an unconfirmed track's count. Confirmed tracks retain confirmation during the tracking grace period, but appear live only while observed. Tracks that never reach 10 observations are never displayed or saved.

The app saves one snapshot per confirmed, measured tracking ID. **Update Measurement** requests a fresh snapshot and replaces the previous cloud, cuboid, and RGB thumbnail if that ID remains in frame. Otherwise, the modal shows **Object not in frame**. The list retains the 20 most recently saved objects, including explicit updates. Records saved before thumbnail support show **No preview** until updated.

A storage host node writes snapshots sequentially without blocking the measurement controller. Only one object from one sequence is submitted, and another save waits for its acknowledgement and a newer sequence. Unsaved visible tracks keep their waiting order. Point-cloud encoding, RGB crop decoding, JPEG encoding, and disk writes run in the storage node. Thumbnails are at most 160 × 120 pixels and fetched once per saved revision; history polls carry only thumbnail availability.

History lives in `OAKAGENT_STORAGE_APP/parcel-measurement.sqlite3` on the OAK4. Host runs use `data/parcel-measurement.sqlite3` beside the script. Use `--storage <database-path>` to choose another location. Saved history survives app restarts. New live tracks start above the persisted ID high-water mark; the app does not identify the same physical parcel across restarts.

## Choose RGB overlays

Enable **Colorized depth over RGB** to blend the public `ApplyDepthColormap` node's colors into RGB at 50% opacity. Colors use the node's 2nd–98th depth percentiles, rather than a fixed metric scale. Invalid depth stays transparent. After selecting a support plane, enable **Show selected support plane** to highlight only its visible inliers in green; parcels and background keep their RGB colors. Enabling either overlay switches the other off. Both default off. A separate preview node caches the calibrated remap and blends textures without blocking measurements. Boxes and labels remain native annotations over the H.264 stream.

The app asks `SupportPlaneCalibrator` to verify the selected plane every five seconds against the current cloud and gravity. If verification fails, measurements pause, the frontend opens **Calibration**, and a warning prompts recalibration. Keep the camera fixed, click **Recalibrate**, and select the supporting surface again.

The app limits the Python OpenCV worker pool to one thread so preview conversions leave CPU capacity for detection and measurement. The normal RGB path decodes no BGR image. Optional previews use active NV12 planes and keep the original frame identity when producing encoded output.

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

NeuralDepth receives the raw mono outputs. ImageAlign's aligned output and exact depth passthrough feed `ImageAlignDepthCorrection` with the explicit source-axial correction policy. Native PointCloud consumes its corrected output and produces an organized 768 × 480 cloud in CAM_A RGB optical coordinates and millimeters. Zero, saturated depth, and nonfinite XYZ become zero organized rows before calibration and are excluded from detector inputs. The app preserves native metadata and stores the matching depth-correction provenance with each new measurement.

One pipeline creates all nodes before startup. Host nodes handle scene admission, IMU conversion, calibration results, parcel results, preview rendering, snapshot storage, and timed benchmark logging. The main loop manages pipeline lifetime. Up to two measurement scenes can remain in flight to absorb timing jitter. Storage still allows only one snapshot job. The first selected plane and later selections reach the detector through `ParcelDetectorConfig` before the next admitted scene.

Raw images and the cloud retain their independent sequence counters and timestamps. Boxes project through the delivered RGB intrinsics, distortion, and pose. Video and annotations carry matching RGB metadata.

Tracking belongs to this app. The node's candidate IDs are frame-local. The app associates centers and box overlap, expires tracks after two seconds, and clears associations after recalibration. IDs can change after occlusion or fast motion.

The detector can miss parcels or classify background clutter as eligible. Use an uncluttered measurement area. This example does not claim metrology accuracy or persistent identity.

## Check the app logic

```bash
python3 -m unittest discover -s tests -v
npm --prefix frontend run build
```

See the [validation record](VALIDATION.md) for completed checks and their limits.
