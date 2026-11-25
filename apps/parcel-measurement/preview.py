from datetime import timedelta

import cv2
import depthai as dai
import numpy as np


def nv12_frame(image, reference):
    height, width = image.shape[:2]
    planar = cv2.cvtColor(image, cv2.COLOR_BGR2YUV_I420).reshape(-1)
    luma_size = width * height
    chroma_size = luma_size // 4
    data = np.empty_like(planar)
    data[:luma_size] = planar[:luma_size]
    data[luma_size::2] = planar[luma_size : luma_size + chroma_size]
    data[luma_size + 1 :: 2] = planar[luma_size + chroma_size :]
    result = dai.ImgFrame()
    result.setType(dai.ImgFrame.Type.NV12)
    result.setWidth(width)
    result.setHeight(height)
    result.setStride(width)
    result.setData(data)
    result.setBufferMetadataFrom(reference)
    result.setTransformation(reference.getTransformation())
    return result


class PreviewRequest(dai.Buffer):
    def __init__(self, frame, depth=False, plane=None, annotations=None):
        super().__init__()
        self.frame = frame
        self.depth = depth
        self.plane = plane
        self.annotations = annotations


class PreviewRenderer:
    def __init__(self):
        self._geometry_key = None
        self._maps = None
        self._plane_texture = None

    def _remap(self, frame):
        projection = frame.projection
        transformation = frame.depth.getTransformation()
        extrinsics = transformation.getExtrinsics()
        raw_extrinsics = frame.color.getTransformation().getExtrinsics()
        depth_size = frame.depth.getWidth(), frame.depth.getHeight()
        target_intrinsics = np.asarray(
            transformation.getIntrinsicMatrix(), dtype=np.float64
        )
        target_pose = np.asarray(
            extrinsics.getTransformationMatrix(False, dai.LengthUnit.MILLIMETER),
            dtype=np.float64,
        )
        distortion = np.asarray(
            transformation.getDistortionCoefficients(), dtype=np.float64
        )
        reference = extrinsics.toDeviceId, extrinsics.toCameraSocket
        raw_reference = raw_extrinsics.toDeviceId, raw_extrinsics.toCameraSocket
        key = (
            projection.size,
            depth_size,
            projection.fisheye,
            np.asarray(projection.intrinsics, dtype=np.float64).tobytes(),
            np.asarray(projection.distortion, dtype=np.float64).tobytes(),
            np.asarray(projection.reference_to_camera, dtype=np.float64).tobytes(),
            target_intrinsics.tobytes(),
            target_pose.tobytes(),
            distortion.tobytes(),
            transformation.getDistortionModel(),
            reference,
            raw_reference,
        )
        if key == self._geometry_key:
            return self._maps
        if reference != raw_reference:
            raise ValueError(
                "Preview RGB and depth need the same calibration reference."
            )
        if (
            transformation.getDistortionModel() != dai.CameraModel.Perspective
            or not np.isfinite(distortion).all()
            or np.any(np.abs(distortion) > 1e-8)
        ):
            raise ValueError("Preview depth must use an undistorted perspective grid.")
        target_from_raw = np.linalg.inv(target_pose) @ np.linalg.inv(
            projection.reference_to_camera
        )
        if not np.allclose(target_from_raw[:3, 3], 0, atol=1e-3, rtol=0):
            raise ValueError(
                "Preview RGB and aligned depth must share an optical center."
            )
        rotation = target_from_raw[:3, :3]
        width, height = projection.size
        rows, columns = np.indices((height, width), dtype=np.float32)
        pixels = np.stack((columns, rows), axis=-1).reshape(-1, 1, 2)
        undistort = (
            cv2.fisheye.undistortPoints if projection.fisheye else cv2.undistortPoints
        )
        mapped = undistort(
            pixels,
            np.asarray(projection.intrinsics, dtype=np.float64),
            np.asarray(projection.distortion, dtype=np.float64),
            R=rotation,
            P=target_intrinsics,
        ).reshape(height, width, 2)
        map_x = np.ascontiguousarray(mapped[:, :, 0])
        map_y = np.ascontiguousarray(mapped[:, :, 1])
        raw_z = rotation[:, 2] @ np.linalg.inv(target_intrinsics)
        front = raw_z[0] * map_x + raw_z[1] * map_y + raw_z[2]
        invalid = ~np.isfinite(map_x) | ~np.isfinite(map_y) | (front <= 0)
        map_x[invalid] = -1
        map_y[invalid] = -1
        self._maps = map_x, map_y
        self._plane_texture = np.empty((*depth_size[::-1], 3), dtype=np.uint8)
        self._plane_texture[:] = (100, 235, 70)
        self._geometry_key = key
        return self._maps

    def render(self, frame, depth=False, plane=None):
        if not depth and plane is None:
            return frame.color
        maps = self._remap(frame)
        values = frame.depth.getFrame()
        valid = (values > 0) & (values < 65535)
        if depth:
            normalized = np.clip(
                (values.astype(np.float32) - 200) * (255 / 2800), 0, 255
            ).astype(np.uint8)
            texture = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
            mask = valid.astype(np.uint8) * 255
        else:
            texture = self._plane_texture
            mask = np.zeros_like(values, dtype=np.uint8)
        if plane is not None:
            distance = np.einsum(
                "ij,j->i",
                frame.points,
                np.asarray(plane.normal, dtype=np.float32),
                optimize=False,
            )
            distance = np.abs(distance + plane.offset_mm)
            on_plane = ((distance < 10) & np.any(frame.points != 0, axis=1)).reshape(
                values.shape
            ) & valid
            plane_mask = on_plane.astype(np.uint8) * 255
            if depth:
                cv2.copyTo(self._plane_texture, plane_mask, texture)
            mask = cv2.bitwise_or(mask, plane_mask)
        layer = cv2.remap(
            texture,
            *maps,
            interpolation=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
        )
        mask = cv2.remap(
            mask, *maps, interpolation=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT
        )
        image = frame.image.copy()
        blended = cv2.addWeighted(image, 0.45, layer, 0.55, 0)
        cv2.copyTo(blended, mask, image)
        return nv12_frame(image, frame.color)


class PreviewRendererNode(dai.node.ThreadedHostNode):
    def __init__(self, current_generation=None):
        super().__init__()
        self.current_generation = current_generation
        self.inputFrames = self.createInput("frames", blocking=False, queueSize=1)
        self.out = self.createOutput(
            "video",
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ],
        )
        self.annotations = self.createOutput(
            "annotations",
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ],
        )

    def _current(self, request):
        return (
            self.current_generation is None
            or request.frame.generation == self.current_generation()
        )

    def run(self):
        renderer = PreviewRenderer()
        while self.isRunning():
            request = self.inputFrames.get(timedelta(seconds=1))
            if request is None or not self._current(request):
                continue
            video = renderer.render(request.frame, request.depth, request.plane)
            if not self.isRunning() or not self._current(request):
                continue
            if request.annotations is not None:
                self.annotations.send(request.annotations)
            self.out.send(video)
