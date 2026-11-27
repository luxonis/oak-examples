import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property

import cv2
import depthai as dai
import numpy as np

from geometry import DEPTH_SIZE, CameraProjection, reference_key


@dataclass
class SceneFrame:
    cloud: dai.PointCloudData
    color: dai.ImgFrame
    left: dai.ImgFrame
    right: dai.ImgFrame
    depth: dai.ImgFrame
    points: np.ndarray
    projection: CameraProjection
    generation: int
    captured_at: str = ""
    axial_correction: dict | None = None

    @cached_property
    def image(self):
        data = self.color.getData()
        width, height = self.color.getWidth(), self.color.getHeight()
        stride = self.color.getStride()
        luminance = np.ndarray(
            (height, width), np.uint8, buffer=data, strides=(stride, 1)
        )
        chroma = np.ndarray(
            (height // 2, width // 2, 2),
            np.uint8,
            buffer=data,
            offset=self.color.getPlaneStride(),
            strides=(stride, 2, 1),
        )
        return cv2.cvtColorTwoPlane(luminance, chroma, cv2.COLOR_YUV2BGR_NV12)

    @property
    def sequence(self):
        return self.cloud.getSequenceNum()


def stamp(message, reference):
    message.setBufferMetadataFrom(reference)
    return message


def jpeg(image):
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise RuntimeError("Could not encode the camera image.")
    return base64.b64encode(encoded).decode("ascii")


def read_scene(group, generation):
    cloud, color, left, right = (
        group[name] for name in ("pointCloud", "color", "left", "right")
    )
    if any(
        reference_key(message) != reference_key(cloud)
        for message in (color, left, right)
    ):
        raise RuntimeError(
            "The cloud and images do not share a calibrated reference frame."
        )
    depth = group["depth"]
    correction = group["axialCorrection"]
    if any(
        message.getSequenceNum() != depth.getSequenceNum()
        or message.getTimestamp() != depth.getTimestamp()
        or message.getTimestampDevice() != depth.getTimestampDevice()
        for message in (cloud, correction.frame)
    ):
        raise RuntimeError(
            "Corrected depth, point cloud, and provenance must identify one frame."
        )
    if (depth.getWidth(), depth.getHeight()) != DEPTH_SIZE:
        raise RuntimeError(
            f"RGB-aligned depth returned {(depth.getWidth(), depth.getHeight())}, expected {DEPTH_SIZE}."
        )
    points = np.array(cloud.getPoints(), dtype=np.float32, copy=True)
    if points.shape != (DEPTH_SIZE[0] * DEPTH_SIZE[1], 3):
        raise RuntimeError(
            f"Expected an organized {DEPTH_SIZE} point cloud, received {points.shape}."
        )
    values = depth.getFrame().reshape(-1)
    invalid = (values == 0) | (values == 65535) | ~np.isfinite(points).all(axis=1)
    points[invalid] = 0
    filtered_cloud = stamp(dai.PointCloudData(), cloud)
    filtered_cloud.setPoints(points)
    filtered_cloud.setTransformation(cloud.getTransformation())
    return SceneFrame(
        cloud=filtered_cloud,
        color=color,
        left=left,
        right=right,
        depth=depth,
        points=points,
        projection=CameraProjection.from_frame(color),
        generation=generation,
        captured_at=datetime.now(timezone.utc).isoformat(),
        axial_correction=correction.provenance.to_dict(),
    )


def object_boxes(batch, projection):
    objects = []
    for item in batch.items:
        points = np.asarray(item.xyz_mm)
        bbox = projection.bounds(points)
        if bbox is not None:
            objects.append(
                {
                    "candidate_id": item.candidate_id,
                    "bbox": bbox,
                    "center_mm": points.mean(axis=0).astype(float).tolist(),
                }
            )
    return objects


def candidate_preview(frame, plane):
    valid = np.isfinite(frame.points).all(axis=1) & (
        np.linalg.norm(frame.points, axis=1) > 0
    )
    distance = np.abs(frame.points @ np.asarray(plane.normal) + plane.offset_mm)
    pixels, _ = frame.projection.project(frame.points[valid & (distance < 10)])
    pixels = np.rint(pixels).astype(np.int32)
    width, height = frame.projection.size
    pixels = pixels[
        (pixels[:, 0] >= 0)
        & (pixels[:, 0] < width)
        & (pixels[:, 1] >= 0)
        & (pixels[:, 1] < height)
    ]
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(pixels):
        mask[pixels[:, 1], pixels[:, 0]] = 255
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    image = frame.image.copy()
    chosen = mask != 0
    image[chosen] = (image[chosen] * 0.35 + np.array((100, 235, 70)) * 0.65).astype(
        np.uint8
    )
    return jpeg(image)


def annotated_image(image, objects):
    result = image.copy()
    scale = max(0.45, image.shape[1] / 1400)
    for detected_object in objects:
        x1, y1, x2, y2 = map(round, detected_object["bbox"])
        dimensions = dimension_label(detected_object)
        cv2.rectangle(
            result, (x1, y1), (x2, y2), (130, 230, 60), max(2, round(scale * 2))
        )
        cv2.putText(
            result,
            f"ID {detected_object['track_id']} | {dimensions}",
            (max(0, x1), max(round(25 * scale), y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (130, 230, 60),
            max(1, round(scale)),
            cv2.LINE_AA,
        )
    return result


def metadata_record(message):
    transformation = message.getTransformation()
    extrinsics = transformation.getExtrinsics()
    return {
        "size": list(transformation.getSize()),
        "intrinsics": transformation.getIntrinsicMatrix(),
        "distortion_model": str(transformation.getDistortionModel()),
        "distortion_coefficients": transformation.getDistortionCoefficients(),
        "pose_to_reference_mm": extrinsics.getTransformationMatrix(
            False, dai.LengthUnit.MILLIMETER
        ),
        "reference": [extrinsics.toDeviceId, extrinsics.toCameraSocket.name],
    }


def native_annotations(frame, objects):
    message = dai.ImgAnnotations()
    annotation = dai.ImgAnnotation()
    width, height = frame.getWidth(), frame.getHeight()
    color = dai.Color()
    color.r, color.g, color.b, color.a = 0.3, 0.9, 0.45, 1
    for detected_object in objects:
        x1, y1, x2, y2 = detected_object["bbox"]
        rectangle = dai.PointsAnnotation()
        rectangle.type = dai.PointsAnnotationType.LINE_LOOP
        rectangle.outlineColor = color
        rectangle.thickness = 2
        rectangle.points = dai.VectorPoint2f(
            [
                dai.Point2f(float(x / width), float(y / height), True)
                for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
            ]
        )
        annotation.points.append(rectangle)
        dimensions = dimension_label(detected_object)
        text = dai.TextAnnotation()
        text.position = dai.Point2f(
            float(x1 / width), float(max(0, y1 - 30) / height), True
        )
        text.text = f"ID {detected_object['track_id']} | {dimensions}"
        text.textColor = color
        background = dai.Color()
        background.r, background.g, background.b, background.a = 0.03, 0.05, 0.07, 0.85
        text.backgroundColor = background
        text.fontSize = 24
        annotation.texts.append(text)
    message.annotations = dai.VectorImgAnnotation([annotation])
    message.setBufferMetadataFrom(frame)
    message.setTransformation(frame.getTransformation())
    return message


def dimension_label(detected_object):
    values = detected_object["dimensions_mm"]
    if not values:
        return detected_object["status"]
    return (
        " x ".join(
            f"{name}: {'?' if value is None else round(value)}"
            for name, value in zip(("L", "W", "H"), values)
        )
        + " mm"
    )
