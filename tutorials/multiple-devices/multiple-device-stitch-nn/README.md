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

The resized inference canvas stays internal. Only the panorama detection stream
is published, so each object has one label and box.

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
`ImgDetections.transformTo()` map tile detections directly to the full panorama
before NMS and display. Camera sources may span multiple
devices; the first device selects the inference model platform.

Inference uses native `dai.node.DetectionNetwork`; NMS uses native
`dai.beta.node.ImgDetectionsFilter` on the host. Tiling, cropping and timestamp
gathering use `depthai-nodes`. The small merge helper preserves the matched
reference transformation when moving detections from tiles to the panorama.


### Performance measurement

Measured on 2026-11-02 against commit `0f17e5fd9`, using DepthAI 3.11.0,
depthai-nodes 0.7.0, a Ryzen 7 5800H host and PoE RVC2 inference. Both versions
received the same captured 1476 × 749 panorama, with two tiles and
`luxonis/yolov6-nano:r2-coco-512x288`. Each version/rate had two 20-second
measurement windows after five seconds of warm-up, in before/after/after/before
order. Values below average the two runs; latency averages their medians.

| Requested FPS | Output FPS before → after | Detection latency before → after | Host CPU before → after |
| --- | --- | --- | --- |
| 5 | 5.0 → 5.0 | 126 → 119 ms | 12.1% → 10.1% |
| 20 | 15.6 → 15.7 | 1486 → 1478 ms | 33.9% → 29.4% |

CPU percentages are relative to one logical core and cover the benchmark process.
Latency runs from panorama submission to final detections. Capture, stitching,
and Visualizer work are excluded. Detection samples matched between versions.
The native path used about 13–16% less CPU, with no meaningful throughput gain;
the small latency differences were within the variation between runs. At a
requested 20 FPS, both paths queued frames because inference could not keep up.
