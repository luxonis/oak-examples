# Native panorama stitching with tiled YOLO detection

Combine overlapping camera streams into a panorama, run tiled YOLO inference,
and display the images and detections in the DepthAI Visualizer.

This example uses **image-content panorama registration** from the
[Luxonis Stitching documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/stitching).
It requires overlapping, textured views rather than inter-camera calibration.
Stitching runs on the host for both **RVC2 and RVC4**; YOLO runs on the first
selected device. This example has no standalone deployment path.

## Run

Requires Python >=3.10 and the pinned dependencies in `requirements.txt`.
The requirements select DepthAI snapshot
`3.12.0.dev0+d4cb5b0f547f42ad39312c0dec48802b41028fa7` from the Luxonis snapshot index.
Native host stitching needs DepthAI with OpenCV support, enabled by default.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# Two physical devices with overlapping views, in left-to-right order:
oakctl run-script python main.py --devices LEFT_DEVICE_ID RIGHT_DEVICE_ID --sockets CAM_A
```

Pass both device IDs or IPs after `--devices`. With `--sockets CAM_A`, this
selects one camera on each device, for two sources total. `--sockets` defaults to
CAM_A and applies to every selected device: `--sockets CAM_B CAM_C` on two
devices would select four sources. To diagnose stitching with two sensors on
just one device, use `--devices DEVICE_ID --sockets CAM_B CAM_C` instead.
Use `-fps` to change the capture rate (default 10) and `-is` to change the
input resolution (default 360p). Run `python main.py --help` for choices.

Open **http://localhost:8082** in the Visualizer:

- `Input-N`: individual camera streams.
- `Stitched` and `PanoramaDetections`: full panorama and detection overlays.

The resized inference canvas stays internal. Only the panorama detection stream
is published, so each object has one label and box.

Press **r** to reset registration after moving cameras, **q** or Ctrl-C to stop.

## How stitching works

Native `dai.node.Stitching` synchronizes the inputs internally. This example
uses PANORAMA mode, evaluates three valid registration candidates, and reuses
the strongest transform for subsequent frames. Failed candidates do not count;
no panorama is emitted until registration succeeds.
`setUseInputCalibration(False)` explicitly selects image-content registration;
the snapshot defaults to calibrated composition.

The settings in `main.py` use a perspective projection, DP_COLOR seams, a
4096x2048 maximum panorama size, and a 100ms synchronization threshold.
Perspective projection suits a narrow combined field of view below 180° and
supports this example's native detection remapping. The size limit rejects
oversized registrations before composition; it does not resize them to fit.
Synchronization groups frames by timestamp and does not align camera exposures.

Use rigidly mounted cameras with substantial overlap and textured scenes.
Wide baselines and nearby objects can cause parallax. If registration fails,
check the input streams and camera placement; there is no concatenation fallback.
See the [Stitching documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/stitching)
for calibrated panorama composition, cylindrical/360° views, planar projection,
seam choices, and synchronization options beyond this example.

## Inference

The native panorama is BGR888i and carries its virtual-camera transformation.
ImageManip resizes it for tiled inference and selects BGR888p for RVC2 or
BGR888i for RVC4. Timestamp-matched references and native
`ImgDetections.transformTo()` map tile detections directly to the full panorama
before NMS and display. Camera sources may span multiple
devices; the first device selects the inference model platform.

Inference uses native `dai.node.DetectionNetwork`. Tiling, cropping, timestamp
gathering and host NMS use `depthai-nodes`. Its `ImgDetectionsFilter.useNms()`
suppresses duplicates within the merged tile detections; the snapshot's native
filter only suppresses duplicates between separate inputs. The small merge helper
preserves the matched reference transformation when moving detections from tiles
to the panorama.
