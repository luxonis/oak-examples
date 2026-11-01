# Native panorama stitching with tiled YOLO detection

Combine overlapping camera streams from RVC2, RVC4, or a mixed rig using
`dai.beta.node.Stitching` in PANORAMA mode. Stitching runs on the host; YOLO runs
on the first selected device. This is a host example, without standalone packaging.
Requires Python >=3.10 and DepthAI 3.11.0 with OpenCV support.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# Choose cameras in a consistent left-to-right order:
oakctl run-script python main.py --devices DEVICE_ID_LEFT DEVICE_ID_RIGHT
# Alternatively, stitch overlapping sensors on one device:
oakctl run-script python main.py --devices DEVICE_ID --sockets CAM_B CAM_C
```

Without `--devices`, all available, unbooted RVC2/RVC4 devices are selected.
Explicit selection is recommended in shared environments. Devices are opened by
ID/IP, never by an implicit discovery choice. Select only devices you can access;
this example does not configure authentication or update devices.

Open http://localhost:8082 in the DepthAI Visualizer. `Input-0`, `Input-1`, etc.
show the selected sources. `Stitched` is the full native panorama; `Inference`
is the fixed, stretched inference canvas. `Patcher` contains NMS-filtered tiled
YOLO detections in canvas coordinates; `PanoramaDetections` maps them back to
the full panorama. Each group is mapped against its timestamp-matched reference
with native `ImgDetections.transformTo()`; this also works on RVC2 and avoids
caching stale panorama geometry after a reset. Native transformations are retained throughout resizing,
cropping, mapping and merging. The native BGR888i output is converted to BGR888p for RVC2 inference and
retained as BGR888i for RVC4 inference. Model YAML paths resolve relative to the script.

Press **r** to call `resetTransform()` after moving cameras. Autofocus (where
available) is enabled again and disabled after five seconds to reduce flicker.
Press **q** or Ctrl-C to stop. All devices belong to one pipeline and close together.

## Registration and limits

Place static cameras with substantial overlap and textured, similarly lit views.
Close foreground objects and motion can cause parallax and seams. Registration
selects the strongest of three valid candidates, then caches the transform and
composition. It uses a perspective projection (required by the current native
detection remapper), DP_COLOR seams and caps panorama dimensions at 4096x2048.

**The old concatenate-on-failure fallback has been removed.** A concatenation
has no single panorama camera geometry. If registration fails, source topics
remain visible but no panorama or detections are emitted. After 20 seconds the
script prints guidance; a bounded run exits unsuccessfully if it produced no
panorama. This avoids displaying an unrelated image as a successful stitch.

The internal Sync threshold defaults to 100ms for independent office cameras.
It groups frames by time; it does not synchronize exposures. Tighten it for
hardware-synchronized cameras. No FPS or seam-quality improvement is assumed.

## Options and validation

Run `python main.py --help` for all options. Existing `-fps` / `--fps_limit` and
`-is` / `--input_size` flags remain; default capture rate is 10 FPS.

```bash
# Camera and native-stitch validation without model download:
oakctl run-script python main.py --devices DEVICE_ID --sockets CAM_B CAM_C \
  --no-nn --duration 60 --reset-after 25
# In a second terminal, capture the live result:
oakctl inspect frames Stitched --count 2 --out evidence/panorama --timeout 30s
# Validate full inference separately by omitting --no-nn.
```

`--estimation-frames`, `--sync-threshold-ms`, `--max-panorama-size WIDTH HEIGHT`,
and `--seam-finder` configure native registration. `--sockets` selects the same
ordered sockets on each device. Duplicate devices or sockets are rejected.

Check weak overlap (source topics but no fabricated panorama), textured overlap
(real panorama), reset after movement, bounded canvas allocation, and detection
alignment on both image sizes. Beta APIs may change; dependency versions are pinned.

[Native Stitching documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/stitching)

Live device results and remaining limits are recorded in [device validation notes](docs/device.md).

RVC2 live panorama:

![RVC2 native panorama](media/native-panorama-rvc2.png)

RVC4 live panorama:

![RVC4 native panorama](media/native-panorama-rvc4.png)
