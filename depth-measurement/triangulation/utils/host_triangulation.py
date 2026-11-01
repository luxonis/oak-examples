import cv2
import depthai as dai
import numpy as np
from depthai_nodes.utils import AnnotationHelper

from .stereo_inference import StereoInference


class Triangulation(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._combinedColor = (1, 0, 0, 1)  # red
        self._leftColor = (0, 1, 0, 1)  # green
        self._rightColor = (0, 0, 1, 1)  # blue
        self.combined_frame = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.disparity_line = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.measurements_info = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.bbox_left = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.keypoints_left = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.bbox_right = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.keypoints_right = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        face_left: dai.Node.Output,
        face_right: dai.Node.Output,
        face_nn_left: dai.Node.Output,
        face_nn_right: dai.Node.Output,
        device: dai.Device,
    ) -> "Triangulation":
        self.link_args(face_left, face_right, face_nn_left, face_nn_right)
        self._stereoInference = StereoInference(
            device.readCalibration().getBaselineDistance(
                dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C, False
            )
            * 10
        )

        return self

    def process(
        self,
        face_left: dai.Buffer,
        face_right: dai.Buffer,
        nn_face_left: dai.Buffer,
        nn_face_right: dai.Buffer,
    ) -> None:
        assert isinstance(face_left, dai.ImgFrame)
        assert isinstance(face_right, dai.ImgFrame)
        assert isinstance(nn_face_left, dai.ImgDetections)
        assert isinstance(nn_face_right, dai.ImgDetections)

        # Inference passthroughs identify exactly which capture produced detections.
        if (
            face_left.getSequenceNum() != nn_face_left.getSequenceNum()
            or face_right.getSequenceNum() != nn_face_right.getSequenceNum()
            or abs(
                (face_left.getTimestamp() - face_right.getTimestamp()).total_seconds()
            )
            > 0.005
        ):
            return
        intrinsics = face_left.getTransformation().getIntrinsicMatrix()
        left_frame = face_left.getCvFrame()
        right_frame = face_right.getCvFrame()

        bbox_annot_left = AnnotationHelper()
        for detection in nn_face_left.detections:
            rect = detection.getBoundingBox()
            x = rect.center.x
            y = rect.center.y
            w = rect.size.width
            h = rect.size.height
            top_left = (x - w / 2, y - h / 2)
            bottom_right = (x + w / 2, y + h / 2)

            bbox_annot_left.draw_rectangle(
                top_left=top_left,
                bottom_right=bottom_right,
                outline_color=self._leftColor,
                thickness=1,
            )

        bbox_annot_left_msg = bbox_annot_left.build(
            timestamp=face_left.getTimestamp(), sequence_num=face_left.getSequenceNum()
        )
        self.bbox_left.send(bbox_annot_left_msg)

        bbox_annot_right = AnnotationHelper()
        for detection in nn_face_right.detections:
            rect = detection.getBoundingBox()
            x = rect.center.x
            y = rect.center.y
            w = rect.size.width
            h = rect.size.height
            top_left = (x - w / 2, y - h / 2)
            bottom_right = (x + w / 2, y + h / 2)

            bbox_annot_right.draw_rectangle(
                top_left=top_left,
                bottom_right=bottom_right,
                outline_color=self._rightColor,
                thickness=1,
            )

        bbox_annot_right_msg = bbox_annot_right.build(
            timestamp=face_right.getTimestamp(),
            sequence_num=face_right.getSequenceNum(),
        )
        self.bbox_right.send(bbox_annot_right_msg)

        combined = cv2.addWeighted(left_frame, 0.5, right_frame, 0.5, 0)
        output_frame = self._create_output_frame(face_left, combined)
        self.combined_frame.send(output_frame)

        y_dimension, x_dimension = combined.shape[:2]

        disparity_line_helper = AnnotationHelper()
        text_helper = AnnotationHelper()
        keypoints_left_helper = AnnotationHelper()
        keypoint_rights_helper = AnnotationHelper()
        if len(nn_face_left.detections) == 1 and len(nn_face_right.detections) == 1:
            keypoints = zip(
                nn_face_left.detections[0].getKeypoints2f(),
                nn_face_right.detections[0].getKeypoints2f(),
            )

            for i, (keypoint_left, keypoint_right) in enumerate(keypoints):
                coords_left = (
                    keypoint_left.x * x_dimension,
                    keypoint_left.y * y_dimension,
                )
                coords_right = (
                    keypoint_right.x * x_dimension,
                    keypoint_right.y * y_dimension,
                )

                rel_coords_left = (
                    coords_left[0] / x_dimension,
                    coords_left[1] / y_dimension,
                )
                rel_coords_right = (
                    coords_right[0] / x_dimension,
                    coords_right[1] / y_dimension,
                )

                # Visualize keypoints
                keypoints_left_helper.draw_circle(
                    center=rel_coords_left,
                    radius=3 / x_dimension,
                    outline_color=self._leftColor,
                    thickness=1,
                )
                keypoint_rights_helper.draw_circle(
                    center=rel_coords_right,
                    radius=3 / x_dimension,
                    outline_color=self._rightColor,
                    thickness=1,
                )
                # Visualize disparity line
                disparity_line_helper.draw_line(
                    pt1=rel_coords_left,
                    pt2=rel_coords_right,
                    color=self._combinedColor,
                    thickness=1,
                )

                # Calculate spatial data
                disparity = coords_left[0] - coords_right[0]
                spatial = self._stereoInference.triangulate(
                    coords_left, coords_right, intrinsics
                )
                if spatial is None:
                    continue

                if i == 0:
                    strings = [
                        f"Disparity: {disparity:.0f} pixels",
                        f"X: {spatial[0] / 1000:.2f} m",
                        f"Y: {spatial[1] / 1000:.2f} m",
                        f"Z: {spatial[2] / 1000:.2f} m",
                    ]
                    y = 0.05
                    y_delta = 0.02
                    for s in strings:
                        text_helper.draw_text(
                            text=s,
                            position=(0.05, y),
                            color=(1.0, 1.0, 1.0, 1.0),
                            background_color=(0.0, 0.0, 0.0, 0.7),
                            size=4,
                        )
                        y += y_delta

        keypoints_left_helper_msg = keypoints_left_helper.build(
            timestamp=face_left.getTimestamp(), sequence_num=face_left.getSequenceNum()
        )
        self.keypoints_left.send(keypoints_left_helper_msg)

        keypoint_rights_helper_msg = keypoint_rights_helper.build(
            timestamp=face_right.getTimestamp(),
            sequence_num=face_right.getSequenceNum(),
        )
        self.keypoints_right.send(keypoint_rights_helper_msg)

        disp_line_msg = disparity_line_helper.build(
            timestamp=face_left.getTimestamp(), sequence_num=face_left.getSequenceNum()
        )
        self.disparity_line.send(disp_line_msg)

        text_helper_msg = text_helper.build(
            timestamp=face_left.getTimestamp(), sequence_num=face_left.getSequenceNum()
        )
        self.measurements_info.send(text_helper_msg)

    def _create_output_frame(
        self, msg: dai.ImgFrame, frame: np.ndarray
    ) -> dai.ImgFrame:
        output_frame = dai.ImgFrame()
        output_frame.setCvFrame(frame, dai.ImgFrame.Type.BGR888i)
        output_frame.setTimestamp(msg.getTimestamp())
        output_frame.setSequenceNum(msg.getSequenceNum())
        output_frame.setTimestampDevice(msg.getTimestampDevice())
        output_frame.setTransformation(msg.getTransformation())
        return output_frame
