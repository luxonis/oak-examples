import cv2
import depthai as dai
import numpy as np
from depthai_nodes.utils import AnnotationHelper


def create_messages(frame, mask, confidence, trail, options):
    """Build native overlays tied to the source frame's metadata.

    Args:
        frame: DepthAI frame that produced the tracking result.
        mask: Boolean target mask at model resolution (320, 576).
        confidence: Target score, clamped to [0, 1] for the bounding box.
        trail: Sequence of normalized (x, y) target centroids.
        options: Boolean switches named mask, box, outline, and trail.

    Returns:
        Tuple of ImgDetections, SegmentationMask, and ImgAnnotations. The
        diagnostic SegmentationMask is populated even when its overlay is off.
    """
    detections = dai.ImgDetections()
    segmentation = dai.SegmentationMask()
    for message in (detections, segmentation):
        message.setTimestamp(frame.getTimestamp())
        message.setTimestampDevice(frame.getTimestampDevice())
        message.setSequenceNum(frame.getSequenceNum())
        message.setTransformation(frame.getTransformation())

    # Native masks can be lower resolution than the frame transformation.
    # Keep model resolution to avoid upscaling identical data for transport.
    binary = mask.astype(np.uint8)
    h, w = binary.shape
    # Native instance masks use index 0 for the target and 255 for background.
    indexed = np.where(binary, 0, 255).astype(np.uint8)
    segmentation.setCvMask(indexed)
    segmentation.setLabels(["Target"])
    if options["mask"]:
        detections.setCvSegmentationMask(indexed)

    yy, xx = np.nonzero(binary)
    if len(xx) and options["box"]:
        detection = dai.ImgDetection()
        detection.label = 0
        detection.labelName = "Target"
        detection.confidence = float(np.clip(confidence, 0, 1))
        detection.xmin, detection.xmax = float(xx.min() / w), float((xx.max() + 1) / w)
        detection.ymin, detection.ymax = float(yy.min() / h), float((yy.max() + 1) / h)
        detections.detections = [detection]

    helper = AnnotationHelper()
    if options["outline"] and len(xx):
        contours, _ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        mh, mw = mask.shape
        for contour in contours:
            if cv2.contourArea(contour) < 8:
                continue
            contour = cv2.approxPolyDP(contour, 1.2, True).reshape(-1, 2)
            if len(contour) >= 3:
                helper.draw_polyline(
                    [(float(x / mw), float(y / mh)) for x, y in contour],
                    outline_color=(0.1, 0.9, 0.65, 1),
                    fill_color=None,
                    thickness=2,
                    closed=True,
                )

    if options["trail"] and len(trail) > 1:
        helper.draw_polyline(
            list(trail), outline_color=(1, 0.72, 0.15, 1), fill_color=None, thickness=3
        )

    annotations = helper.build(frame.getTimestamp(), frame.getSequenceNum())
    annotations.setTimestampDevice(frame.getTimestampDevice())
    annotations.setTransformation(frame.getTransformation())
    return detections, segmentation, annotations
