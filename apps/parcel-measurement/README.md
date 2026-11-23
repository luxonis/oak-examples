# Measure parcels with an OAK4

This example shows RGB parcel boxes, temporary tracking IDs, and length × width × height in millimeters. The frontend starts support-plane calibration and lets you select a candidate surface.

The app uses public `ParcelDetector`, `ParcelDimensioner`, and `SupportPlaneCalibrator` nodes from the pinned revision of [depthai-nodes PR 348](https://github.com/luxonis/depthai-nodes/pull/348). Capture defaults to 10 FPS with the recommended unrectified RGB at 2000 × 1500, unrectified left/right at 1280 × 800, and NeuralDepth LARGE at 768 × 480. RGB uses NV12 to reduce camera-link traffic.

## Run on your computer

Use an OAK4 with RGB, stereo, and an IMU. Install `oakctl`, then create an isolated Python 3.12 environment in this directory.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
oakctl run-script .venv/bin/python main.py --device <OAK4-IP>
```

Open [the parcel frontend](http://localhost:8082).

1. Keep the camera fixed and show the horizontal surface supporting the parcels.
2. Click **Find support planes**.
3. Inspect each candidate preview. Green pixels mark projected plane inliers. Choose the supporting table or floor rather than a parcel top.
4. Click **Use this support plane**.
5. Keep parcels separated and fully in view. Eligible parcels receive boxes with tracking IDs and dimensions.

Recalibrate after moving the camera or changing the support surface. Unknown heights appear as `?`. Failed frames show a failure reason instead of fabricated dimensions.

The frontend distinguishes the configured capture FPS, the observed source FPS, and measurement throughput. Capture runs at 10 FPS by default. Parcel detection and measurement run on the host CPU, and their rate depends on the host and scene. The app keeps one scene in flight and joins each overlay to its matching RGB frame.

## Run as an OAK App

From this directory, run the packaged app on an OAK4.

```bash
oakctl app run .
```

The packaged app explicitly binds the frontend and inspection server to all device interfaces. The host script defaults to localhost. The frontend listens on port 8082 and needs no Node.js build. Standalone performance depends on the device CPU and scene.

## Inspect and save evidence

Start with `--evidence evidence` to save delivered metadata, the selected plane, RGB, an annotated image, and structured results locally.

```bash
oakctl run-script .venv/bin/python main.py --device <OAK4-IP> --evidence evidence
oakctl inspect topics
oakctl inspect frames "Parcel overlay" --count 1 --out evidence/inspect
```

The topics are RGB, Depth, and Parcel overlay. `/api/state` exposes the capture profile, calibration state, and rates. `/ws` carries RGB-plus-overlay snapshots. Parcel messages remain same-host objects.

## Geometry and tracking

NeuralDepth receives the raw mono outputs and performs its internal stereo processing. Native PointCloud uses the 768 × 480 depth grid with DEFAULT coordinates, millimeters, calibrated translation, and an identity custom transform. XYZ already occupies the common reference identified by its metadata. The app preserves that metadata when filtering detector input points.

Raw RGB, mono images, and depth/cloud data synchronize on the shared device clock. Image sequence counters stay independent. The detector reads intrinsics, distortion, and poses directly from native metadata and handles scene synchronization. RGB boxes and plane previews use the full delivered camera model, including lens distortion and the inverse RGB pose.

The calibrator receives an organized cloud. Processed accelerometer specific force is rotated into that cloud's reference using the RGB pose rotation. After selection, the parcel pipeline builds with the actual `SupportPlane`. Later selections use `ParcelDetectorConfig` updates on `inputConfig`; unchanged scenes retain the selected plane.

Tracking belongs to this app. The node's candidate IDs are frame-local. The app associates centers and box overlap, expires tracks after two seconds, and clears associations after recalibration. IDs can change after occlusion or fast motion.

The geometric detector can miss a parcel or classify background clutter as eligible. Use an uncluttered measurement area. The app preserves the public node outcomes without private configuration changes. This example does not claim metrology accuracy or persistent identity.

## Check the app logic

```bash
python3 -m unittest discover -s tests -v
```

The tests cover calibration selection, stale candidates, repeated attempts, tracking associations, distorted RGB projection, camera poses, and IMU reference conversion. See the [validation record](VALIDATION.md) for live checks and their limits.
