import base64
from dataclasses import dataclass

import cv2
import depthai as dai
import numpy as np

from geometry import CameraProjection, reference_key

DEPTH_SIZE = (768, 480)


@dataclass
class SceneFrame:
    cloud: dai.PointCloudData
    color: dai.ImgFrame
    left: dai.ImgFrame
    right: dai.ImgFrame
    image: np.ndarray
    points: np.ndarray
    projection: CameraProjection
    generation: int

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
    if (depth.getWidth(), depth.getHeight()) != DEPTH_SIZE:
        raise RuntimeError(
            f"NeuralDepth returned {(depth.getWidth(), depth.getHeight())}, expected {DEPTH_SIZE}."
        )
    points = np.asarray(cloud.getPoints(), dtype=np.float32)
    if points.shape != (DEPTH_SIZE[0] * DEPTH_SIZE[1], 3):
        raise RuntimeError(
            f"Expected an organized {DEPTH_SIZE} point cloud, received {points.shape}."
        )
    return SceneFrame(
        cloud,
        color,
        left,
        right,
        color.getCvFrame(),
        points,
        CameraProjection.from_frame(color),
        generation,
    )


def parcel_boxes(batch, projection):
    parcels = []
    for item in batch.items:
        points = np.asarray(item.xyz_mm)
        bbox = projection.bounds(points)
        if bbox is not None:
            parcels.append(
                {
                    "candidate_id": item.candidate_id,
                    "bbox": bbox,
                    "center_mm": points.mean(axis=0).astype(float).tolist(),
                }
            )
    return parcels


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


def annotated_image(image, parcels):
    result = image.copy()
    scale = max(0.45, image.shape[1] / 1400)
    for parcel in parcels:
        x1, y1, x2, y2 = map(round, parcel["bbox"])
        values = parcel["dimensions_mm"]
        dimensions = (
            " x ".join("?" if v is None else str(round(v)) for v in values) + " mm"
            if values
            else parcel["status"]
        )
        cv2.rectangle(
            result, (x1, y1), (x2, y2), (130, 230, 60), max(2, round(scale * 2))
        )
        cv2.putText(
            result,
            f"ID {parcel['track_id']} | {dimensions}",
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


def native_annotations(frame, parcels):
    message = dai.ImgAnnotations()
    annotation = dai.ImgAnnotation()
    width, height = frame.getWidth(), frame.getHeight()
    color = dai.Color()
    color.r, color.g, color.b, color.a = 0.3, 0.9, 0.45, 1
    for parcel in parcels:
        x1, y1, x2, y2 = parcel["bbox"]
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
        values = parcel["dimensions_mm"]
        dimensions = (
            " x ".join("?" if value is None else str(round(value)) for value in values)
            + " mm"
            if values
            else parcel["status"]
        )
        text = dai.TextAnnotation()
        text.position = dai.Point2f(
            float(x1 / width), float(max(0, y1 - 30) / height), True
        )
        text.text = f"ID {parcel['track_id']} | {dimensions}"
        text.textColor = color
        text.fontSize = 24
        annotation.texts.append(text)
    message.annotations = dai.VectorImgAnnotation([annotation])
    message.setBufferMetadataFrom(frame)
    message.setTransformation(frame.getTransformation())
    return message
