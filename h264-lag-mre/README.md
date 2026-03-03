# H264 Lag MRE

MRE for an H.264 stream lag regression on RVC4 in standalone mode.

## Bug Description

When multiple high-resolution streams are active simultaneously, the H.264 encoded stream starts to lag noticeably. When one stream is closed, the lagging stops. The issue goes away when stream resolutions are lowered.

**Observed behavior:**
- Lowering the second stream resolution (e.g. 640×480 instead of 1280×720) eliminates the lag.

## Pipeline

- **Camera A** → 1440×1080 NV12 → visualizer ("Raw NV12") + H.264 encoder → visualizer ("H264")
- **Camera A** → 1280×720 BGR888i → visualizer ("Raw BGR") ← *triggers lag*

Replacing the 1280×720 output with 640×480 eliminates the lag, confirming the issue is throughput-dependent.

## Reproducing

To reproduce the lag run in standalone mode on an RVC4 device:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```
