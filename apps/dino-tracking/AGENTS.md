# AGENTS.md

## Summary

This is the best standalone reference for class-free interactive tracking based on segmentation plus DINO similarity. Use it when you need click-to-select tracking without predefined classes and want the backend to own the tracking state while the frontend controls visualization.

## Use This Example When

- You need interactive object selection from the live stream.
- You want similarity heatmaps or bbox outputs driven by DINO embeddings.
- You need a strong reference for backend/frontend state synchronization.
- You want a custom standalone app where the only published stream is a rendered video output.

## Do Not Use This Example When

- You need predefined-class object detection.
- You need dataset snapping or measurement rather than tracking.
- You need host/peripheral support instead of standalone-only RVC4 packaging.
- You need a minimal tracker without custom services and custom host-side logic.

## Quick Facts

- `Category:` `apps/dino-tracking`
- `Shape:` `frontend`
- `Primary task:` interactive similarity-based tracking from FastSAM masks and DINO embeddings
- `Entrypoint:` [backend/src/main.py](backend/src/main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` [frontend/src/App.tsx](frontend/src/App.tsx)
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; static frontend build; model downloads for FastSAM and DINO
- `Input:` live RGB camera plus click prompts from the frontend
- `Output:` one encoded `Video` stream with overlays
- `Models:` `luxonis/fastsam-s:512x288` and `luxonis/dinov3-backbone:convnext-small-640x480` from [backend/src/constants/nn.yaml](backend/src/constants/nn.yaml)
- `Visualizer / UI:` custom static frontend

## Read First

- [backend/src/main.py](backend/src/main.py): full pipeline and service registration
- [backend/src/constants/camera.yaml](backend/src/constants/camera.yaml): camera resolution and FPS defaults
- [backend/src/constants/nn.yaml](backend/src/constants/nn.yaml): model names and input sizes
- [backend/src/constants/reference_adaptation.yaml](backend/src/constants/reference_adaptation.yaml): adaptive-reference tuning
- [backend/src/object_selection/mask_selection_node.py](backend/src/object_selection/mask_selection_node.py): mask selection from click prompts
- [backend/src/dino_similarity/reference_vectors/reference_vector_from_selection_node.py](backend/src/dino_similarity/reference_vectors/reference_vector_from_selection_node.py): initial reference extraction
- [backend/src/dino_similarity/reference_vectors/adaptive_reference_vector_node.py](backend/src/dino_similarity/reference_vectors/adaptive_reference_vector_node.py): online reference adaptation
- [backend/src/detections_tracking/heatmap_to_detections_node.py](backend/src/detections_tracking/heatmap_to_detections_node.py): bbox extraction from similarity heatmaps
- [backend/src/annotations/detections_annotation_overlay_node.py](backend/src/annotations/detections_annotation_overlay_node.py): final overlay rendering
- [backend/src/FE_state_synchronization_service.py](backend/src/FE_state_synchronization_service.py): backend-to-frontend state export
- [frontend/src/App.tsx](frontend/src/App.tsx): click handling and UI state restore
- [frontend/src/AnnotationModeSelector.tsx](frontend/src/AnnotationModeSelector.tsx): heatmap versus bbox mode
- [frontend/src/OutlinesToggle.tsx](frontend/src/OutlinesToggle.tsx): FastSAM outline toggle
- [oakapp.toml](oakapp.toml): static frontend build and backend packaging

## Architecture

- One RGB camera feeds three branches: display, segmentation, and DINO embedding extraction.
- FastSAM segmentation produces masks.
- A frontend click chooses the target mask.
- DINO grid features plus the selected mask produce a reference vector.
- An adaptive-reference node updates that target representation over time.
- Similarity heatmaps are converted into detections, tracked, and rendered as overlays.
- The frontend controls annotation mode, threshold, and outline visibility through services.

## Data Flow

- `RGB -> FastSAM parsing NN -> mask selection`
- `RGB -> DINO NN -> grid features`
- `mask selection + grid features -> reference vector -> adaptive reference`
- `adaptive reference + grid features + RGB -> similarity heatmap`
- `similarity heatmap -> detections -> tracker -> overlay -> encoded Video`

## Modification Guide

- `Safe to change:` frontend labels, threshold defaults, annotation mode defaults, outline toggle behavior, YAML constants
- `Requires care:` click-coordinate handling, mask-to-reference-vector logic, adaptive-reference tuning, tracker input/output assumptions
- `Likely to break if changed blindly:` backend/frontend state sync, the one-stream rendered-output design, or the relationship between heatmap and bbox modes

## Common Adaptations

- `To change camera or model sizes:` start in [backend/src/constants/](backend/src/constants/)
- `To disable adaptation:` edit [backend/src/constants/reference_adaptation.yaml](backend/src/constants/reference_adaptation.yaml) and the adaptive-reference wiring in [backend/src/main.py](backend/src/main.py)
- `To replace the tracker:` keep the selection and similarity pipeline, then swap [backend/src/detections_tracking/tracker.py](backend/src/detections_tracking/tracker.py)
- `To build a different frontend:` keep the registered service names stable or update both backend and frontend together

## Constraints

- This example is RVC4 standalone only.
- Initial startup may take longer because model assets must become available before the `Video` topic appears.
- The frontend intentionally waits for the `Video` topic before enabling stream interaction.
- Backend state is authoritative; the frontend restores state from `BE State Service` rather than owning it locally.

## Non-Obvious Repo Conventions

- Only one encoded `Video` topic is published; intermediate masks, heatmaps, and detections are not exposed as separate topics.
- The custom frontend assumes service names like `Click Prompt Service`, `Clear Selection Service`, `Threshold Update Service`, `Outlines Trigger Service`, `Annotation Mode Service`, and `BE State Service`.
- The example keeps its tuning in YAML files instead of burying everything in `main.py`, so constants belong under [backend/src/constants/](backend/src/constants/).

## Related Examples

- [apps/data-collection](https://github.com/luxonis/oak-examples/tree/main/apps/data-collection): use this when you need interactive prompting and backend state sync but not similarity tracking
- [apps/people-demographics-and-sentiment-analysis](https://github.com/luxonis/oak-examples/tree/main/apps/people-demographics-and-sentiment-analysis): use this when you need another standalone frontend app with richer backend state
- [neural-networks/object-tracking/deepsort-tracking](https://github.com/luxonis/oak-examples/tree/main/neural-networks/object-tracking/deepsort-tracking): use this when you need a class-based tracking reference
- [apps/focused-vision](https://github.com/luxonis/oak-examples/tree/main/apps/focused-vision): use this when your main problem is preserving detail rather than selecting and tracking an object

## Validation

- `Run:` `oakctl app run .`
- `Success looks like:` the frontend shows the video stream, clicks select a target, and switching between heatmap and bbox views changes the backend-rendered overlay
- `Common failure meaning:` the `Video` topic never becomes available, model assets are unavailable, or service names drifted between backend and frontend
