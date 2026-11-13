# AGENTS.md

## Summary

Save short RVC4 diagnostic captures containing native DAI frames, calibration and previews from available RGB, stereo and ToF sensors, using host or standalone mode.

## Use This Example When

Need camera recordings for diagnostics or replay, including processed ToF depth and confidence.

## Do Not Use This Example When

Need RVC2, raw ToF, generated stereo depth, hardware synchronization or continuous recording.

## Quick Facts

Python 3.10+, DepthAI >=3.11,\<4; `main.py` runs on the host, `oakapp.toml` supplies the standalone entrypoint.

## Read First

Read `README.md` for commands and compatibility notes, then `main.py` for pipeline and capture behavior.

## Architecture

- `main.py`: camera roles, pipeline, timestamp grouping, capture state and native file writes.
- `control.py` and `index.html`: HTTP controls, previews and standalone ZIP downloads.
- `preview.py`: renders saved frames without changing their original data.
- `standalone.sh` installs `nginx-site.template` before oakapp-base starts. Build-time changes outside `/app` did not persist on all tested agents. Keep proxy ports 8083/8082/8765 aligned with the backend and Visualizer.

## Constraints

- Detect ToF by sensor type; cameras and stereo pairs are optional.
- Preserve original calibration, full-FOV unrectified images and native DAI messages. Preview-only GRAY8-to-RAW8 relabelling must not change saved frames.
- Preserve per-stream directories and shared numeric filename keys for replay. Sync groups device timestamps; it does not synchronize exposures.
- Only a complete manifest means success. Keep partial data and failure metadata, including when stopped by SIGTERM.
- Standalone output must stay within `$OAKAGENT_STORAGE_APP/captures`. ZIP entries must come from the completed manifest, never arbitrary paths.
- Capture controls use loopback on the host and same-origin device-IP HTTPS in standalone mode. Downloads are shown only in standalone mode; Hub/WebRTC controls are unsupported.

## Related Examples

- https://github.com/luxonis/oak-examples/tree/main/tutorials/camera-demo

## Validation

From this directory, run `python -m unittest discover -s tests`.

For pipeline changes, capture on idle RGB-only, stereo and ToF devices; reload the DAI files and check geometry, frame count and manifest completion. For standalone changes, also verify HTTPS controls, live streams, ZIP contents and persistence after restart. Record OS and dai versions; stop only the test app.
