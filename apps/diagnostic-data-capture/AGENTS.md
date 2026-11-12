# AGENTS.md

## Summary

Capture short RVC4 diagnostic recordings on the host or in persistent on-device storage with automatic optional-camera detection, native DAI files and a DepthAI Visualizer preview.

## Use This Example When

Need calibration plus RGB/left/right and processed ToF depth/confidence for diagnostics or replay.

## Do Not Use This Example When

Need RVC2, raw ToF, stereo depth generation, hardware synchronization or sustained gap-free recording.

## Quick Facts

- Host + standalone on RVC4. Python 3.10+, DepthAI >=3.11; `main.py` is the entrypoint.
- Five frame sets and five seconds warmup by default.
- Host GUI at loopback port 8083 embeds SDK Visualizer on 8082/8765. Standalone uses the oak-agent assigned HTTPS frontend port.
- Startup prints only the capture GUI URL; `create_visualizer` filters the SDK's generic URL banner during construction while preserving other output.

## Read First

- `README.md`, `main.py`, `control.py`, `oakapp.toml`, `standalone.sh`, `nginx-site.template`.

## Architecture

- `main.py`: discovers camera roles, owns pipeline/queues, groups frame sets with a host `Sync` node, writes native messages/calibration/metadata.
- `control.py`: loopback stdlib HTTP server; enqueues requests and streams the latest complete capture as ZIP without a temporary archive.
- `oakapp.toml`: runs `standalone.sh`, which installs the proxy template before starting `main.py --standalone` through oakapp-base. `nginx-site.template` routes controls, downloads, Visualizer assets and `/dai` WebSocket through one HTTPS origin.
- `index.html`: capture controls, polling, saved preview and embedded Visualizer.
- `preview.py`: builds preview.jpg from the first saved DAI frame set; original frames remain unchanged.

## Constraints

- Standalone requires `OAKAGENT_STORAGE_APP`; captures are restricted to its `captures` subdirectory, never the ephemeral app filesystem. Host output remains configurable.
- Use `--build-arg DEPTHAI_VERSION=3.11.0` for the tested ToF device on OS 1.38.1; SDK 3.12.1 could not open its on-device connection. Default builds use the requirements range.
- Standalone control requests accept same-origin device IP URLs, not arbitrary hostnames. Hub/WebRTC capture controls are not implemented.
- Keep internal ports 8083 (controls), 8082 (Visualizer), and 8765 (WebSocket) aligned with the proxy.
- ZIP contents come only from a completed capture manifest plus calibration/metadata/preview; never expose arbitrary paths or directory listings.
- Handle SIGTERM through the normal cleanup path for partial-capture metadata and device release.
- Camera sockets are optional; ToF is detected from sensor type, never treated as RGB.
- Never introduce StereoDepth or save raw ToF in this example.
- Preserve original calibration and full-FOV, unrectified camera geometry for replay.
- Only completed captures count as successful. Preserve partial data with failure metadata.
- Keep files out of source control; never interrupt another camera user's workload.

## Related Examples

- https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo
- https://github.com/luxonis/oak-examples/tree/main/tutorials/multiple-devices/multiple-devices-preview

## Validation

Run `python -m unittest discover -s tests` for role/control/request checks with the existing SDK. Hardware: run bounded `--auto-capture --no-gui` on idle RGB-only, stereo and ToF devices; reload every DAI, verify count and geometry, inspect GUI capture and saved path. Record actual device ID, OS, SDK, durations and failures.

Standalone: use `oakctl app run . -d CAMERA_IP` on an idle device, verify HTTPS controls and live Visualizer, capture five sets, download and reload every DAI in the ZIP, and verify persistent files after a stop/start. Stop only the app started for validation.
