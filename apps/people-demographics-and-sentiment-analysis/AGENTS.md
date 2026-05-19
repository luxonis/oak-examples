# AGENTS.md

## Summary

This is the strongest standalone reference in the repo for multi-stage people analytics: face detection, age/gender, emotion, re-identification, people tracking, and a frontend that polls a summarized backend state. Use it when you need a user-facing analytics app rather than a single-task face example.

## Use This Example When

- You need multiple face-related second-stage models in one app.
- You need to join face features with tracked people over time.
- You want a frontend that shows last-seen faces and aggregate stats instead of only stream overlays.
- You need a standalone RVC4 app rather than a simple host-side face demo.

## Do Not Use This Example When

- You need only one face model such as age/gender or emotion recognition.
- You need an open-vocabulary or click-driven UI.
- You need generic object tracking rather than person analytics.
- You need a peripheral-first example with no static frontend.

## Quick Facts

- `Category:` `apps/people-demographics-and-sentiment-analysis`
- `Shape:` `frontend`
- `Primary task:` people analytics with face features, re-id, and frontend stats
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` intended RVC4 standalone path only
- `Requires:` RVC4 device; static frontend build; bundled and Zoo-downloaded face/people models
- `Input:` one RGB camera stream
- `Output:` `Video`, `Annotations`, and `Get Faces` service payloads for the face strip and stats panel
- `Models:` Yunet face detection, emotion recognition, age-gender recognition, YOLOv6 Nano people detection, and ArcFace re-id from [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py)
- `Visualizer / UI:` custom static frontend

## Read First

- [backend/src/main.py](backend/src/main.py): full pipeline, model loading, joining, and service/topic publication
- [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py): FPS and model defaults
- [backend/src/faces/face_detection.py](backend/src/faces/face_detection.py): face detection stage
- [backend/src/faces/cropping/face_crops_node.py](backend/src/faces/cropping/face_crops_node.py): crop generation for second-stage models
- [backend/src/nn/second_stage_nn.py](backend/src/nn/second_stage_nn.py): age/gender, emotion, and re-id stage wrapper
- [backend/src/people/people_tracking.py](backend/src/people/people_tracking.py): people tracking stage
- [backend/src/people/joiner/people_faces_join.py](backend/src/people/joiner/people_faces_join.py): join logic between tracked people and face features
- [backend/src/visualization/monitor_node.py](backend/src/visualization/monitor_node.py): `Get Faces` service payload generation
- [backend/src/visualization/annotation_node.py](backend/src/visualization/annotation_node.py): overlay rendering
- [frontend/src/App.tsx](frontend/src/App.tsx): main layout
- [frontend/src/useFacePoll_load.tsx](frontend/src/useFacePoll_load.tsx): `Get Faces` polling and UI update logic
- [frontend/src/StatsBanner.tsx](frontend/src/StatsBanner.tsx): aggregate stats display
- [frontend/src/FaceMetaBar.tsx](frontend/src/FaceMetaBar.tsx): per-face metadata strip
- [oakapp.toml](oakapp.toml): static frontend build and backend packaging

## Architecture

- A camera source node produces preview and encoded video.
- Face detection finds candidate faces.
- Cropping logic creates face crops for second-stage models.
- Separate second-stage NNs estimate emotions, age/gender, and re-id embeddings.
- A people tracker runs on the full frame.
- Join logic associates face features with tracked people.
- Visualization nodes render annotations and export the last-seen face cards plus aggregate stats through a service.

## Data Flow

- `RGB -> face detector -> face crops -> emotion / age-gender / re-id second-stage NNs`
- `RGB -> people tracker -> tracklets`
- `face features + tracklets -> joiner -> analytics state`
- `analytics state -> annotation node -> Annotations`
- `analytics state -> monitor node -> Get Faces service payload`

## Modification Guide

- `Safe to change:` FPS default, frontend layout, service polling cadence, model names, face-card presentation
- `Requires care:` join logic between faces and people, second-stage output formats, face-crop/reference synchronization, service payload schema
- `Likely to break if changed blindly:` the frontend polling contract, face-to-track association behavior, or multi-stage synchronization

## Common Adaptations

- `To change models:` start in [backend/src/config/system_configuration.py](backend/src/config/system_configuration.py)
- `To change how many faces are shown in the UI:` inspect [backend/src/visualization/monitor_node.py](backend/src/visualization/monitor_node.py) and [frontend/src/App.tsx](frontend/src/App.tsx)
- `To reuse only the analytics backend:` keep the join and monitor nodes, then replace the frontend with another service consumer
- `To study just one subtask:` compare against the face-specific examples under [neural-networks/face-detection](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection)

## Constraints

- The intended runtime is RVC4 standalone only.
- The backend defaults to `15` FPS if no limit is provided.
- The frontend updates the face strip and stats by polling `Get Faces` once per second.
- Only three face tiles are displayed in the frontend even if more people are in view.

## Non-Obvious Repo Conventions

- [backend/src/config/arguments.py](backend/src/config/arguments.py) still exposes `--device` for development, but the indexed and documented path for this example is standalone-only.
- The frontend does not derive face metadata from stream topics; it depends on the `Get Faces` service from [backend/src/visualization/monitor_node.py](backend/src/visualization/monitor_node.py).
- The static frontend path is active here, unlike the partially wired frontend tree in [apps/focused-vision](https://github.com/luxonis/oak-examples/tree/main/apps/focused-vision).

## Related Examples

- [apps/dino-tracking](https://github.com/luxonis/oak-examples/tree/main/apps/dino-tracking): use this when you need another standalone frontend/backend app with backend-owned state
- [neural-networks/face-detection/age-gender](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/age-gender): use this when you only need age/gender
- [neural-networks/face-detection/emotion-recognition](https://github.com/luxonis/oak-examples/tree/main/neural-networks/face-detection/emotion-recognition): use this when you only need emotion recognition
- [neural-networks/reidentification/human-reidentification](https://github.com/luxonis/oak-examples/tree/main/neural-networks/reidentification/human-reidentification): use this when the main task is re-id rather than a user-facing analytics app

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend shows the annotated stream, the face strip updates as people appear, and aggregate stats change over time
- `Common failure meaning:` the app is not running on RVC4, one of the second-stage models is unavailable, or the `Get Faces` service payload no longer matches the frontend expectation
