from typing import List
import depthai as dai

from depthai_nodes import ImgDetectionsExtended
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

    def build(self, gather_data_msg) -> "AnnotationNode":
        self.link_args(gather_data_msg)
        return self

    def process(self, gather_data_msg) -> None:
        detections_msg: ImgDetectionsExtended = gather_data_msg.reference_data
        assert isinstance(detections_msg, ImgDetectionsExtended)
        src_w, src_h = detections_msg.transformation.getSize()

        gaze_msg_list: List[dai.NNData] = gather_data_msg.gathered
        assert isinstance(gaze_msg_list, list)
        assert all(isinstance(rec_msg, dai.NNData) for rec_msg in gaze_msg_list)
        assert len(gaze_msg_list) == len(detections_msg.detections)

        annotations = AnnotationHelper()

        for detection, gaze in zip(detections_msg.detections, gaze_msg_list):
            face_bbox = detection.rotated_rect.getPoints()
            keypoints = detection.keypoints

            # Draw bbox
            annotations.draw_rectangle(
                [face_bbox[0].x, face_bbox[0].y], [face_bbox[2].x, face_bbox[2].y]
            )

            # Draw gaze
            gaze_tensor = gaze.getFirstTensor(dequantize=True)
            gaze_tensor = gaze_tensor.flatten()

            left_eye = keypoints[0]
            annotations.draw_line(
                [left_eye.x, left_eye.y],
                self._get_end_point(left_eye, gaze_tensor, src_w, src_h),
            )

            right_eye = keypoints[1]
            annotations.draw_line(
                [right_eye.x, right_eye.y],
                self._get_end_point(right_eye, gaze_tensor, src_w, src_h),
            )

        annotations_msg = annotations.build(
            timestamp=detections_msg.getTimestamp(),
            sequence_num=detections_msg.getSequenceNum(),
        )

        self.out.send(annotations_msg)

    def _get_end_point(
        self, start_point: dai.Point2f, vector: list, src_w: int, src_h: int
    ) -> dai.PointsAnnotation:
        gaze_vector = (vector * 640)[:2]
        gaze_vector_x = gaze_vector[0] / src_w
        gaze_vector_y = gaze_vector[1] / src_h
        end_point = [
            start_point.x + gaze_vector_x.item(),
            start_point.y - gaze_vector_y.item(),
        ]
        return end_point
