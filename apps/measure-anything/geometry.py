from dataclasses import dataclass

import cv2
import depthai as dai
import numpy as np


DEPTH_SIZE = (768, 480)


@dataclass(frozen=True)
class CameraProjection:
    size: tuple[int, int]
    intrinsics: np.ndarray
    distortion: np.ndarray
    reference_to_camera: np.ndarray
    fisheye: bool = False

    @classmethod
    def from_frame(cls, frame):
        metadata = frame.getTransformation()
        if not metadata.isValid() or metadata.getSize() != (
            frame.getWidth(),
            frame.getHeight(),
        ):
            raise ValueError("The RGB frame is missing delivered-pixel calibration.")
        pose = np.asarray(
            metadata.getExtrinsics().getTransformationMatrix(
                False, dai.LengthUnit.MILLIMETER
            )
        )
        model = metadata.getDistortionModel()
        if model not in (dai.CameraModel.Perspective, dai.CameraModel.Fisheye):
            raise ValueError(f"Unsupported RGB projection model: {model}")
        return cls(
            size=(frame.getWidth(), frame.getHeight()),
            intrinsics=np.asarray(metadata.getIntrinsicMatrix()),
            distortion=np.asarray(metadata.getDistortionCoefficients()),
            reference_to_camera=np.linalg.inv(pose),
            fisheye=model == dai.CameraModel.Fisheye,
        )

    def project(self, points):
        points = np.asarray(points, dtype=np.float64)
        optical = (
            points @ self.reference_to_camera[:3, :3].T
            + self.reference_to_camera[:3, 3]
        )
        visible = np.isfinite(optical).all(axis=1) & (optical[:, 2] > 0)
        if not visible.any():
            return np.empty((0, 2)), visible
        if self.fisheye:
            pixels, _ = cv2.fisheye.projectPoints(
                optical[visible].reshape(-1, 1, 3),
                np.zeros(3),
                np.zeros(3),
                self.intrinsics,
                self.distortion,
            )
        else:
            pixels, _ = cv2.projectPoints(
                optical[visible],
                np.zeros(3),
                np.zeros(3),
                self.intrinsics,
                self.distortion,
            )
        return pixels.reshape(-1, 2), visible

    def bounds(self, points):
        pixels, _ = self.project(points)
        pixels = pixels[np.isfinite(pixels).all(axis=1)]
        if not len(pixels):
            return None
        minimum = np.maximum(pixels.min(axis=0), (0, 0))
        maximum = np.minimum(pixels.max(axis=0), np.asarray(self.size) - 1)
        if np.any(maximum <= minimum):
            return None
        return [
            float(minimum[0]),
            float(minimum[1]),
            float(maximum[0]),
            float(maximum[1]),
        ]


def reference_key(message):
    extrinsics = message.getTransformation().getExtrinsics()
    return extrinsics.toDeviceId, extrinsics.toCameraSocket


def transformed_imu(message, rotation):
    result = dai.IMUData()
    result.setBufferMetadataFrom(message)
    packets = []
    for packet in message.packets:
        original = packet.acceleroMeter
        vector = rotation @ np.array((original.x, original.y, original.z))
        report = dai.IMUReportAccelerometer()
        report.x, report.y, report.z = map(float, vector)
        report.timestamp = original.timestamp
        report.tsDevice = original.tsDevice
        report.tsSystem = original.tsSystem
        report.sequence = original.sequence
        report.accuracy = original.accuracy
        transformed = dai.IMUPacket()
        transformed.acceleroMeter = report
        packets.append(transformed)
    result.packets = packets
    return result
