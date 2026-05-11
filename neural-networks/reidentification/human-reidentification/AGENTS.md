# AGENTS.md

## Summary

This is the repository reference for person or face re-identification using interchangeable detector and embedding models. Use it when you need identity matching across frames rather than plain detections or tracking.

## Use This Example When

- You need person or face re-identification.
- You want a two-stage detect-then-embed pipeline with configurable mode.
- You need camera or replay input with packaged standalone support.

## Do Not Use This Example When

- You only need tracking IDs.
- You need pose estimation instead of identity embeddings.
- You need a single fixed task rather than a face-versus-pose mode switch.

## Quick Facts

- `Category:` `neural-networks/reidentification/human-reidentification`
- `Shape:` `script+standalone`
- `Primary task:` person or face re-identification
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` detector plus embedding model pair for either `pose` or `face` mode
- `Input:` camera frames by default or `ReplayVideo` via `--media_path`
- `Output:` `Video` and `Objects`
- `Models:` SCRFD person/face and OSNet/ArcFace YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/identification.py](utils/identification.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- `--identify pose` selects person detection plus OSNet embeddings.
- `--identify face` selects face detection plus ArcFace embeddings.
- `FrameCropper` extracts crops for the embedding model.
- `GatherData` joins embeddings back with detections, and [utils/identification.py](utils/identification.py) performs the host-side identity matching and annotation.

## Constraints

- The cosine-similarity threshold defaults differ sharply by mode: `0.8` for pose and `0.1` for face in [main.py](main.py).
- This is identity matching, not persistent object tracking.
- The requested frame size is deliberately larger than the detector input to preserve crop quality for the embedding stage.

## Related Examples

- [../../object-tracking/deepsort-tracking](../../object-tracking/deepsort-tracking/): use this when you need embeddings for online tracking instead of identity matching
- [../../pose-estimation/human-pose](../../pose-estimation/human-pose/): use this when you need pose landmarks instead of embeddings
- [../../face-detection/age-gender](../../face-detection/age-gender/): use this when you need another face crop pipeline without identity matching

## Validation

- `Run:` `python3 main.py --identify pose`
- `Alternative run:` `python3 main.py --identify face`
- `Success looks like:` the Visualizer shows `Video` and `Objects`, and repeated appearances of the same subject receive consistent identity labeling
- `Common failure meaning:` the chosen mode does not match the scene, the similarity threshold is inappropriate, or the detector/embedding pair is mismatched
