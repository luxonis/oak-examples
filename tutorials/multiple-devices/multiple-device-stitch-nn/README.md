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
Native host stitching needs DepthAI with OpenCV support, enabled by default.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# Overlapping cameras, in left-to-right order:
oakctl run-script python main.py --devices LEFT_DEVICE_ID RIGHT_DEVICE_ID

# Or overlapping sensors on one device:
oakctl run-script python main.py --devices DEVICE_ID --sockets CAM_B CAM_C
```

Select at least two camera sources. `--devices` accepts device IDs or IPs;
`--sockets` defaults to CAM_A and applies to each selected device.
Use `-fps` to change the capture rate (default 10) and `-is` to change the
input resolution (default 360p). Run `python main.py --help` for choices.

Open **http://localhost:8082** in the Visualizer:

- `Input-N`: individual camera streams.
- `Stitched` and `PanoramaDetections`: full panorama and detection overlays.
- `Inference` and `Patcher`: resized inference canvas and its detection overlays.

Press **r** to reset registration after moving cameras, **q** or Ctrl-C to stop.

## How stitching works

Native `dai.beta.node.Stitching` synchronizes the inputs internally. This example
uses PANORAMA mode, evaluates three valid registration candidates, and reuses
the strongest transform for subsequent frames. Failed candidates do not count;
no panorama is emitted until registration succeeds.

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
`ImgDetections.transformTo()` map tile detections to the inference canvas for
NMS, then back to the full panorama for display. Camera sources may span multiple
devices; the first device selects the inference model platform.
