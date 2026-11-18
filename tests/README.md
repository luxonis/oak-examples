# Examples Testing

We can test every example in a way where we verify that it is running for a certain period on a specific platform, python, and depthai version.

## U07 crop scheduling validation

The hardware-free regression suite uses DepthAI 3.11.0 and depthai-nodes 0.8.0.
It exercises the SDK's Python matching methods and native messages with synthetic
queues and a controlled clock, without constructing or starting a pipeline:

```bash
DEPTHAI_TELEMETRY=0 python3 -m unittest discover -s tests -p test_crop_gathering.py -v
```

Local result on 18 November 2026: all 12 tests passed with Python 3.12.3,
DepthAI 3.11.0 and depthai-nodes 0.8.0 on Linux, without a device. The grouping
checks exercise all four examples' local gatherer implementations.

It covers zero/one/12 detections, delayed crops followed by empty frames,
results arriving before references, lost crops, late results, expiry with idle
inputs, pending-frame and orphan-result limits, empty decoder results, rotated
barcode ROI expansion, parent indices across multiple vehicles/plates,
multi-head face results, and missing-tile recovery with frame references.
These are message-level checks; they do not establish device crop quality,
model output parity, decoder backend parity, or performance.

All four U07 examples keep identical local `GatherCrops` subclasses so
each example remains independently copyable/packageable. They retain the SDK's
matching/counting implementation, emit complete groups in source timestamp
order, and discard whole incomplete frames after two seconds or when more than
64 reference frames are pending. At most 64 orphan results are retained. Late
results for completed/discarded frames are ignored. Adjust the class constants
for slower workloads and recheck the regression suite when upgrading the SDK.
Per-crop inference uses blocking inputs and one inference thread to preserve
result count and order, including all three people-demographics model branches.

### U07 example dispositions and device checks

| Example                                      | Disposition                                                                                                                                         | Full application validation still required                                                 |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `barcode-detection-conveyor-belt`            | Replace retry/reuse scheduler with `FrameCropper`; bounded `GatherCrops` joins one decoder result per region.                                       | RVC2 peripheral and RVC4 peripheral/standalone; camera/replay; pyzbar and zxing-cpp paths. |
| `license-plate-recognition`                  | Replace both Script crop stages with `FrameCropper`; preserve vehicle/plate indices and task-specific ROI selection.                                | RVC4 peripheral/standalone; camera/replay; compare crop geometry and OCR association.      |
| `people-demographics-and-sentiment-analysis` | Replace generated Script/ImageManip scheduler with `FrameCropper`; use bounded grouping for crops and all three model branches.                     | RVC4 standalone; verify face cards and all three feature results stay associated.          |
| `focused-vision`                             | Replace generated display-crop scheduler with `FrameCropper`; use bounded grouping for two-stage and tiled inference; retain black fallback frames. | RVC4 standalone; compare naive, two-stage and tiling outputs.                              |

For every supported path, exercise zero/one/many detections, slow second stages,
dropped frames and recovery, and rotated regions. Include multiple vehicles
with multiple plate candidates for ALPR. Record device/SDK versions, input,
decoder backend, observed outputs and any fallback. No speedup is claimed.

### Synthetic hardware pipeline results

Passed on 18 November 2026 with Python 3.12.3, DepthAI 3.11.0 and
depthai-nodes 0.8.0. The RVC4 was an OAK4-D R7 running OS 1.45.0.
These checks ran host pipelines over Ethernet; no application bundles were built.

| Platform/path                 | Exercised behavior                                                                                                                                                           | Result                                                                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| RVC2 peripheral               | Real `FrameCropper` with generic and expanded barcode ROIs; 0/1/12 detections, a 20-degree rotated region, 20 ms per-crop probe delay, and one intentionally missing result. | Passed crop count, source metadata and order checks. Incomplete sequence 5 expired; sequences 6 and 7 resumed, producing `[0, 1, 2, 3, 4, 6, 7]`. |
| RVC4 peripheral               | Same crop/group cases with interleaved BGR frames.                                                                                                                           | Passed the same assertions and dropped-result recovery.                                                                                           |
| RVC4 app pipeline components  | Actual focused-vision display cropper and people-demographics face cropper/three-face limiter; fan-out to three delayed host probes in place of the second-stage models.     | Passed 0/1/12-detection cases, crop dimensions, metadata and per-branch recovery after suppressing sequence 5 results.                            |
| RVC4 ALPR pipeline components | Actual vehicle and plate `FrameCropper` stages and ROI selectors; synthetic plate detections/OCR probes; 0/1/12 vehicles and two plate candidates per vehicle.               | Passed selected parent indices, crop/OCR association and source-coordinate checks for every emitted frame.                                        |

The probes substitute for model inference and barcode decoding. Live camera/replay
comparisons, pyzbar/zxing-cpp behavior and packaged RVC4 standalone runs remain
pending in the application matrix above.

### Additional candidate search

Searched Python and C++ sources under `apps`, `camera-controls`, `cpp`,
`custom-frontend`, `depth-measurement`, `integrations`, `neural-networks`,
`streaming` and `tutorials` for generated Scripts, ImageManip crop configs,
image skip/reuse calls, `FrameCropper` and `GatherData`.
No further standard detection-to-crop scheduler was identified beyond the four
initial examples; the remaining implementations have the dispositions below.

| Remaining implementation                                                    | U07 disposition                                                                                                                                          |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `camera-controls/lossless-zooming/utils/crop_face.py`                       | Retain smoothed, fixed-size face-centered NV12 zoom windows. This is a camera/encoder control policy rather than a standard second-stage detection crop. |
| `neural-networks/pose-estimation/hand-pose/utils/process.py`                | Already uses `FrameCropper.fromManipConfigs` and `GatherData`; retain its padded, axis-aligned palm ROI policy.                                          |
| `neural-networks/face-detection/gaze-estimation/utils/process_keypoints.py` | Already uses shared crop/group nodes; retain keypoint-derived left/right eye and face ROI generation.                                                    |
| `neural-networks/ocr/general-ocr/utils/host_process_detections.py`          | Already uses shared crop/group nodes; retain text-specific expansion, size/confidence selection, rotation and white crop background.                     |
| QR/tiling examples and multi-device stitched inference                      | Already use shared crop/group nodes; retain tile-layout configuration.                                                                                   |
| `tutorials/display-detections/crop_highres.py` and full-FOV resize controls | Retain fixed demonstration crop and interactive resize configuration; neither schedules per-detection crops.                                             |
| Other Script nodes                                                          | Networking, NN data handling, LED control or FPS policy; no further crop scheduler to migrate.                                                           |

## Installation

To install the requirements you can do:

```bash
pip install -r requirements.txt
```

## Usage

If you want to run the tests locally we recommend you navigate to the root directory and then run the same command that is running in the Dockerfile:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/
```

This will run all the examples (i.e. folders that have `main.py` and `requirements.txt` present). The outputs will be seen in the CLI and will also be logged into the `out.log` file.

All example tests disable DepthAI telemetry with `DEPTHAI_TELEMETRY=0`. The peripheral runner sets it in each example subprocess after applying `--environment-variables`, so a conflicting value cannot enable telemetry. The standalone runner passes `--env DEPTHAI_TELEMETRY=0` to `oakctl app run` to set it inside the app container on the device. These settings apply to direct pytest runs, Docker/HIL jobs, and the Linux/macOS and Windows test scripts.

**Note:** Because `root-dir` can also accept list of arguments always specify it last, don't use `=` after it and when list is complete use `--` to mark the end (as see in the examples).

You can also pass other custom options to the pytest command. Here is a list of all the custom ones:

```
  --root-dir=ROOT_DIR   One or more paths to directories containing examples (space-separated)..
  --timeout=TIMEOUT     Timeout for script execution (default: 30s).
  --depthai-version=DEPTHAI_VERSION
                        Specify a depthai version to override requirements.txt.
  --depthai-nodes-version=DEPTHAI_NODES_VERSION
                        Specify a depthai-nodes version to override requirements.txt. Can be either released version or branch from GH.
  --environment-variables=ENVIRONMENT_VARIABLES
                        List of additional environment variables (format: VAR1=VAL1 VAR2=VAL2).
  --virtual-display     Enable virtual display (sets DISPLAY=':99'). Only used for peripheral tests.
  --platform={rvc2,rvc4}
                        Specify a platform this is tested on (rvc2 or rvc4). Only used for filtering test examples.
  --python-version={3.8,3.10,3.12}
                        Specify a python version this is tested with (3.8, 3.10 or 3.12). Only used for filtering test examples.
  --strict-mode={yes,no}
                        If set to 'yes', tests will fail on DepthAI warnings.
  --device=DEVICE       Device to perform standalone tests on. If testing just peripheral then not required.
  --device_password=DEVICE_PASSWORD
                        Specify device password. If testing just peripheral then not required.
```

**Note:** The platform and Python values are only used for filtering examples that are known to fail on some combinations when run locally. When run through GitHub workflow on a HIL setup these are taken into account (we build an image with a specific Python version and take a device from the specified platform).

For Linux standalone tests, both test workflows accept an optional `oakctl_version` input. Leave it empty to install the latest release, or set a specific version. Direct Docker builds support the same override with `--build-arg OAKCTL_VERSION=<version>`.

**Note:** If you want to run only peripheral or only standalone tests then set full path to those tests in pytest command. Eg. to only test peripheral:

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir . -- tests/test_examples_peripheral.py
```

If you for example want to run the test on a single example you can do it like this which will run it only on the `generic example`.

```bash
pytest -v -r a --log-cli-level=INFO --log-file=out.log --color=yes --root-dir neural-networks/generic-example -- tests/
```

## Known Failing Examples (Rule System)

Some examples are known to fail under specific conditions (platform, OS, mode, Python
version, DepthAI version, etc.). These are defined in [`constants.py`](./constants.py) inside the
`KNOWN_FAILING` dictionary. During test execution, these rules are evaluated and any
example that matches a failing rule is skipped with the provided reason.

### Rule System Overview

Each failing example contains:

- `reason` – A human-readable explanation of why the example is expected to fail.
- `rules` – A tree of logical conditions describing under which environments the
  example should be treated as failing.

### Rule Tree Structure

A rule tree is composed of logical groups:

```json
{ "and": [ <rules> ] }
{ "or":  [ <rules> ] }
```

- `"and"` — All rules inside must match for the example to be considered failing.
- `"or"`  — Any rule inside may match for the example to be considered failing.

**Every rule block must contain either an `"and"` or `"or"` group**, even when there
is only a single condition.

### Leaf Rules

Leaf rules describe a single condition and take the form:

```json
{ "<condition_name>": <failing_value> }
```

Leaf rules **must contain exactly one condition**.

Supported condition names and values:

| Field             | Allowed Values Example                             | Meaning                                    |
| ----------------- | -------------------------------------------------- | ------------------------------------------ |
| `mode`            | `"all"` or `["peripheral"]`, `["standalone"]`      | Test mode fails under these values         |
| `platform`        | `"all"` or `["rvc2"]`, `["rvc4"]`                  | Hardware platform conditions               |
| `python_version`  | `"all"` or `["3.8"]`, `["3.10"]`, `["3.12"]`       | Python versions that are failing           |
| `depthai_version` | `"all"` or version spec: `">3.0.0rc1"`, `"<3.1.0"` | Fails if DepthAI version matches condition |
| `os`              | `"all"` or `["mac"]`, `["win"]`, `["linux"]`       | Operating system where this fails          |

**A leaf returns True (→ failing) when the current environment matches its
condition.**

### Examples

#### 1. Fail only when running in peripheral mode

```json
"rules": {
    "and": [
        { "mode": ["peripheral"] }
    ]
}
```

#### 2. Fail only on RVC4 devices

```json
"rules": {
    "and": [
        { "platform": ["rvc4"] }
    ]
}
```

#### 3. Fail when platform is RVC2 **or** OS is mac

```json
"rules": {
    "or": [
        { "platform": ["rvc2"] },
        { "os": ["mac"] }
    ]
}
```

#### 4. Fail under both conditions (mode=all AND platform=all)

```json
"rules": {
    "and": [
        { "mode": "all" },
        { "platform": "all" }
    ]
}
```

#### 5. Mixed logic:

Fail when **(mode=all AND platform=rvc2)** OR **(platform=all)**

```json
"rules": {
    "or": [
        {
            "and": [
                { "mode": "all" },
                { "platform": ["rvc2"] }
            ]
        },
        { "platform": "all" }
    ]
}
```

### How Tests Use These Rules

During test collection and filtering:

1. The current environment (mode, platform, python, os, DepthAI version) is collected.
2. Each example’s rule tree is evaluated recursively.
3. If the rules evaluate to `True`, the example is marked as a known failing case and is
   skipped with the associated reason.
4. Otherwise, the example is tested normally.

This system makes it easy to describe complex skip logic without hard-coding behavior
inside the test runner.
