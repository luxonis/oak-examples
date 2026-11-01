# Device validation — 2026-11-01

Host: Linux, Python 3.12, DepthAI 3.11.0, depthai-nodes 0.7.0. Runs used
`oakctl run-script /tmp/oak-u02-venv/bin/python`; that existing isolated environment
already matched requirements and was not modified. No credentials, updates,
flashing, persistent settings changes, or deployments were used.

Live state changes: discover again before reusing a unit. Prefer device IDs;
`1944301051FB078C00` moved from 10.11.1.172 to 10.11.1.171 during this session.
Do not take these addresses as permanent reservations or availability guarantees.

## Successful live runs

All four units ran this example with `--sockets CAM_B CAM_C`, native host
PANORAMA/Perspective stitching and tiled YOLO inference on the selected device.
All panorama images and detection JSONL used below were opened/parsed.

| Platform | Device ID | Observed address | Sample panorama | Messages observed by app |
| --- | --- | --- | --- | --- |
| RVC2 | 1944301021AF721300 | 10.11.1.103 | 700x394; 667x365 after reset | 549 panoramas / 547 inference results in 55s run |
| RVC2 | 1944301051FB078C00 | 10.11.1.171 | 819x542 | 327 panoramas / 322 inference results in 35s run |
| RVC4 | 3155104876 | 10.11.0.55 | 908x562 | 613 panoramas / 612 inference results in 65s run |
| RVC4 | 3121428587 | 10.11.0.62 | 646x362 | 337 panoramas / 336 inference results in 35s run |

Counts include registration time and are not a controlled latency/FPS benchmark.
The RVC2 `.103` and RVC4 `.55` runs called `resetTransform()` after 25/30s.
The RVC2 post-reset detection sample carries the new 667x365 geometry, rather
than retaining the old panorama transformation.

The `.171` snapshot contains a model airplane on a desk; sampled detections
include `airplane` confidence 0.57 in the matching image region. The `.62`
snapshot contains chairs and a person-shaped cardboard display; sampled results
include chair (~0.62) and person (~0.90). The `.103` ceiling and `.55` dim shelf
samples have empty detection results. These stationary snapshots check mapping
plausibility, not detection accuracy or moving-object synchronization.

## Reproduction

The app now uses the Visualizer directly, with no validation queues, counters,
focus timers, or diagnostic CLI flags. Automated checks use a separate script.
The runs and frame counts above were collected before that simplification.
The simplified app was then retested using scripts/validate.py on RVC2
1944301051FB078C00 and RVC4 3121428587. Both produced two real panoramas,
an inference frame, and two full-panorama detection messages, then closed.
Captured geometry was 649x372 on RVC2 and 646x362 on RVC4; RVC4 samples
included chair/person detections. Captures were opened and JSONL parsed under
`/home/matic/Luxonis/oak-examples-u19/evidence/u19-simplified/`.

From the example directory in an environment with its requirements:

```bash
python scripts/validate.py --devices 1944301021AF721300 --sockets CAM_B CAM_C
python scripts/validate.py --devices 1944301051FB078C00 --sockets CAM_B CAM_C
python scripts/validate.py --devices 3155104876 --sockets CAM_B CAM_C
python scripts/validate.py --devices 3121428587 --sockets CAM_B CAM_C
```

Run these sequentially. For manual reset testing, run main.py with the same
device/socket options, press r in the Visualizer, and capture from another terminal:

```bash
oakctl inspect frames Stitched --count 1 --out evidence/panorama --timeout 20s
oakctl inspect frames Inference --count 1 --out evidence/inference --timeout 10s
oakctl inspect dump PanoramaDetections --count 2 --timeout 10s
```

This session's logs, image captures, JSONL and crash archive are in
`/home/matic/Luxonis/oak-examples-u19/evidence/u19/`. The `rvc2-171`, `rvc2-103`,
`rvc4-055-nn`, and `rvc4-062` subdirectories hold the successful captures.

## Mixed devices and failure behavior

A single pipeline opened RVC2 `1944301021AF721300` and RVC4 `3155104876`
simultaneously and streamed each CAM_A source. The views do not share usable
content: one points at a ceiling, the other is nearly black. Registration did
not produce a panorama; the 25s bounded run reported failure without inventing
a concatenated panorama. This proves mixed source transport/construction and
the failure path, not successful stitching or inference across a mixed rig.
An overlapping, physically arranged mixed rig is still needed for that claim.

The installed inspector cannot decode NV12 Input topics. A temporary evidence
adapter (`evidence/u19/capture_inputs.py`) decoded those real frames with
`ImgFrame.getCvFrame()` / OpenCV instead. Native Stitched and Inference topics
were captured directly by oakctl inspect. Source formats were not changed to
hide this inspector limitation.

Other observations: `.105` has no CAM_B; `.205` could not initially be opened
and was later advertised as booted, so it was left alone. Some units briefly
vanish while returning to bootloader after closing.

## Shutdown investigation

The first successful `.103` run logged a firmware crash report while closing.
The archived report contains watchdog error 9001 and two reports with uptimes
~27s/~21s, shorter than the successful 55s run. These may be retained from
preceding aborted development runs; that attribution is an inference. Preserve
`evidence/u19/rvc2-103-crash.tar.gz` rather than treating this as a clean exit.
The second RVC2 `.171` run and mixed-device shutdown did not report a crash.
The original `.103` command was repeated with `DEPTHAI_LEVEL=debug`: it
produced 549 panoramas and 547 inference messages, reset registration, and
closed without a new device-crash/error report. The shutdown failure was not
reproduced. See `evidence/u19/rvc2-103-debug-repeat.log`.

## Local checks

- Two device-free regression tests validate crop-to-panorama boxes, unchanged
  source messages, all reference timestamps, and rejection of missing geometry.
- Example AGENTS structure and generated INDEX checks pass.
- Ruff formatting and checks pass with the pre-existing non-executable shebang
  rule (EXE001) excluded.
- The repository's peripheral test selects this example but skips it because
  its generic runner does not support multi-device testing; live commands above
  provide the execution evidence.

Not validated: camera movement/parallax, a physically overlapping mixed-device
rig, maximum-size rejection under a deliberately degenerate registration, or
comparative seam quality/latency against the former third-party implementation.
