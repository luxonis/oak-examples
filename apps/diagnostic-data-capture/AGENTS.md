# AGENTS.md

## Summary
Capture short RVC4 diagnostic recordings directly on the host with automatic optional-camera detection, native DAI files and a DepthAI Visualizer preview.

## Use This Example When
Need calibration plus RGB/left/right and processed ToF depth/confidence for diagnostics or replay.

## Do Not Use This Example When
Need RVC2, standalone storage, raw ToF, stereo depth generation, hardware synchronization or sustained gap-free recording.

## Quick Facts
- Host Python 3.10+, DepthAI >=3.11; `main.py` is the entrypoint.
- Five frame sets and five seconds warmup by default.
- GUI at loopback port 8083 embeds SDK Visualizer on 8082/8765.

## Read First
- `README.md`, `main.py`, `control.py`.

## Architecture
- `main.py`: discovers camera roles, owns pipeline/queues, matches device timestamps, writes native messages/calibration/metadata.
- `control.py`: loopback stdlib HTTP server; enqueues requests without touching hardware.
- `index.html`: capture controls, polling, saved preview and embedded Visualizer.
- `preview.py`: builds preview.jpg from the first saved DAI frame set; original frames remain unchanged.

## Constraints
- Camera sockets are optional; ToF is detected from sensor type, never treated as RGB.
- Never introduce StereoDepth or save raw ToF in this example.
- Preserve original calibration and full-FOV, unrectified camera geometry for replay.
- Only completed captures count as successful. Preserve partial data with failure metadata.
- Keep files out of source control; never interrupt another camera user's workload.

## Related Examples
- https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo
- https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview

## Validation
Run `python -m unittest discover -s tests` for matching/control/persistence checks with the existing SDK. Hardware: run bounded `--auto-capture --no-gui` on idle RGB-only, stereo and ToF devices; reload every DAI, verify count and geometry, inspect GUI capture and saved path. Validate a left/right capture with the external cv-methods Neural Large replay. Record actual device ID, OS, SDK, durations and failures. In Katka's workspace, build/install dependencies only on tomas/server; local hardware uses existing runtime.
