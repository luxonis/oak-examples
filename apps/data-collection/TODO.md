# TODO

## Frontend: bump `@luxonis/depthai-viewer-common` for segmentation mask rendering

The backend runs `depthai-nodes` 0.6.0, whose `YOLOExtendedParser` attaches instance
segmentation masks to the `dai.ImgDetections` messages sent to the visualizer
(`setCvSegmentationMask`). The masks survive the whole host-side chain
(`ImgDetectionsFilter` re-indexes them, `DetectionsLabelMapper` passes them through),
so the "Annotations" topic already carries them.

They are **not rendered** in the browser, though: the frontend pins
`@luxonis/depthai-viewer-common@1.5.53` (`frontend/package.json`), which depends on
`@luxonis/visualizer-protobuf@2.68.9` — a wire schema that predates `SegmentationMask`
entirely, so the mask field is silently dropped on deserialization.

Fix: bump `@luxonis/depthai-viewer-common` to 3.x (3.7.5 verified to have
`SegmentationMask` support via `visualizer-protobuf` 3.1.14). The API surface used by
this app (`DepthAIContext`, `Streams`, `useDaiConnection`, `./styles`,
`connection.postToService`) still exists in 3.7.5, but it is a 2-major jump —
expect minor prop/styling breakage and possible peer-dep friction with
`@luxonis/common-fe-components` (dvc 3.x moved to `@luxonis/ui-components` internally).
