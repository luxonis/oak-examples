# AGENTS.md

## Summary

This is the repository reference for stitching multiple camera feeds into one panorama-like host view and then running tiled YOLO inference on that stitched image. Use it when you need the repo’s most elaborate multi-device visual-composition tutorial.

## Use This Example When

- You need a host-stitched multi-camera view.
- You want homography-based stitching plus object detection.
- You need a conceptual example for combining multiple devices into one wide scene.

## Do Not Use This Example When

- You need calibrated world-frame fusion instead of image stitching.
- You need a packaged or standalone deployment path.
- You need support for arbitrary camera ordering or moving cameras.

## Quick Facts

- `Category:` `tutorials/multiple-devices/multiple-device-stitch-nn`
- `Shape:` `multi-device-host`
- `Primary task:` stitch multiple device feeds and run tiled YOLO detections over the stitched image
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Frontend:` none
- `Runs on:` host mode only, with at least two discoverable devices of the same practical type/platform
- `Requires:` overlapping FOV, vertically aligned cameras, host CPU headroom, and the `stitching` Python package
- `Input:` live `CAM_A` from each discovered device
- `Output:` `Stitched` image topic and `Patcher` detection overlays
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/stitch.py](utils/stitch.py)
- [utils/merge_img_detections.py](utils/merge_img_detections.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- [main.py](main.py) creates one camera pipeline per device, then feeds all outputs into the threaded [utils/stitch.py](utils/stitch.py) host node.
- [utils/stitch.py](utils/stitch.py) estimates homography/camera parameters once, unless `recalculate_homography()` is triggered with `r`.
- The stitched output is tiled and passed through YOLOv6 so detections cover the wide panorama in smaller NN-sized chunks.
- Autofocus is briefly re-enabled after startup and after each homography recalculation, then turned back off to avoid visible focus flicker in the panorama.

## Constraints

- This is host-only; there is no standalone packaging path.
- Reliable stitching assumes static, vertically aligned cameras with sufficient overlap and consistent left-to-right ordering.
- The code selects the YOLO model variant from the current platform variable after device setup, so mixed-platform multi-device runs are not the intended shape.
- If stitching fails, [utils/stitch.py](utils/stitch.py) falls back to a simple horizontal concatenation.

## Related Examples

- [../multiple-devices-preview](../multiple-devices-preview/): use this when you need per-device outputs without stitching
- [../spatial-detection-fusion](../spatial-detection-fusion/): use this when you need world-frame fused detections instead of a panorama image
- [../../qr-with-tiling](../../qr-with-tiling/): use this when you need tiling as the main idea but not multi-device stitching

## Validation

- `Run:` `python3 main.py`
- `Recalculate:` focus the Visualizer and press `r`
- `Success looks like:` the Visualizer shows a stitched panorama with detection overlays, and pressing `r` recomputes alignment
- `Common failure meaning:` camera overlap/order is wrong, the host lacks enough CPU for stitching plus tiling, or the user expects a robust production stitcher instead of a conceptual tutorial
