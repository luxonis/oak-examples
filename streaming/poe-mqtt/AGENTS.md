# AGENTS.md

## Summary

This is the repository reference for publishing detection telemetry to MQTT directly from the pipeline. Use it when you need broker-integrated object-count messages rather than a video stream.

## Use This Example When

- You need MQTT messages emitted from the running pipeline.
- You want detection-derived telemetry instead of image transport.
- You need a reference for using a `Script` node with a vendored MQTT client.

## Do Not Use This Example When

- You need RTSP, MJPEG, TCP, or WebRTC video delivery.
- You need rich structured detection payloads.
- You need host-side broker logic instead of device-side publication.

## Quick Facts

- `Category:` `streaming/poe-mqtt`
- `Shape:` `script+standalone`
- `Primary task:` publish rolling detection-count averages to MQTT
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` network-reachable devices; intended for PoE deployment, with RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging supported by the example layout
- `Requires:` reachable MQTT broker, YOLOv6 model assets, and script-node network access
- `Input:` live camera by default or `ReplayVideo` via `--media_path`
- `Output:` MQTT publishes plus `Video` and `Detections` visualizer topics
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer plus any MQTT client/subscriber

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/arguments.py](utils/arguments.py)
- [utils/paho-mqtt.py](utils/paho-mqtt.py)
- [oakapp.toml](oakapp.toml)

## Architecture

- [main.py](main.py) runs YOLOv6 on camera or replay input and publishes normal visualizer topics for `Video` and `Detections`.
- A `Script` node on `LEON_CSS` receives parsed detections and embeds the vendored MQTT client from [utils/paho-mqtt.py](utils/paho-mqtt.py).
- The script keeps a rolling total and frame count, then publishes the average number of detections every `10` seconds.
- Broker host, port, topic, username, and password are interpolated into the generated script text at startup.

## Constraints

- The payload is only the average detection count over the last `10` seconds, not raw detections or class-level summaries.
- The default broker/topic pair is public test infrastructure: `test.mosquitto.org:1883` and `test_topic/detections`.
- MQTT credentials are passed into the generated script body in [main.py](main.py), so treat this as a simple example rather than a hardened secret-management pattern.

## Related Examples

- [../mjpeg-streaming](../mjpeg-streaming/): use this when you need image transport instead of telemetry
- [../rtsp-streaming](../rtsp-streaming/): use this when you need a standard live video endpoint
- [../../neural-networks/counting/people-counter](../../neural-networks/counting/people-counter/): use this when your main goal is counting logic rather than broker transport

## Validation

- `Run:` `python3 main.py`
- `Broker override:` `python3 main.py --broker <HOST> --port 1883 --topic my/topic`
- `Success looks like:` the Visualizer shows `Video` and `Detections`, and an MQTT subscriber receives numeric average-count messages roughly every `10` seconds
- `Common failure meaning:` the broker is unreachable from the runtime, the topic or credentials are wrong, or the user expects per-detection events rather than aggregated counts
