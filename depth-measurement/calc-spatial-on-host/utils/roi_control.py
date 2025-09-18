import math
import depthai as dai
from depthai_nodes.utils import AnnotationHelper
from .measure_distance import SpatialDistance
from .measure_distance import RegionOfInterest


class ROIControl(dai.node.HostNode):
    INITIAL_ROI = RegionOfInterest.from_size(100, 100, 5)

    def __init__(self):
        super().__init__()

        self._roi = self.INITIAL_ROI
        self.step = 3

        self.output_roi = self.createOutput()
        self.passthrough = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.annotation_output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def build(
        self,
        disparity_frames: dai.Node.Output,
        measured_depth: dai.Node.Output,
    ) -> "ROIControl":
        self.link_args(disparity_frames, measured_depth)
        return self

    def process(self, disparity: dai.ImgFrame, depth: dai.Buffer) -> None:
        assert isinstance(depth, SpatialDistance)

        annotations_builder = AnnotationHelper()

        annotations_builder.draw_text(
            text="Use 'w', 'a', 's', 'd' keys to move ROI.\nUse 'r' and 'f' to change ROI size.",
            position=(0.02, 0.05),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=4,
        )

        width = disparity.getWidth()
        height = disparity.getHeight()

        rel_xmin = self._roi.xmin / width
        rel_ymin = self._roi.ymin / height
        rel_xmax = self._roi.xmax / width
        rel_ymax = self._roi.ymax / height

        annotations_builder.draw_rectangle(
            top_left=(rel_xmin, rel_ymin),
            bottom_right=(rel_xmax, rel_ymax),
            outline_color=(1, 1, 1, 1),
            thickness=1,
        )

        x = self._roi.xmax
        y = self._roi.ymin

        text_x = (
            f"X: {depth.spatials.x / 1000:.1f}m"
            if not math.isnan(depth.spatials.x)
            else "X: --"
        )
        text_y = (
            f"Y: {depth.spatials.y / 1000:.1f}m"
            if not math.isnan(depth.spatials.y)
            else "Y: --"
        )
        text_z = (
            f"Z: {depth.spatials.z / 1000:.1f}m"
            if not math.isnan(depth.spatials.z)
            else "Z: --"
        )

        text_offset_x = 2
        text_offset_y_1 = 4
        text_offset_y_2 = 8
        text_offset_y_3 = 12

        annotations_builder.draw_text(
            text=text_x,
            position=((x + text_offset_x) / width, (y + text_offset_y_1) / height),
            color=(1, 1, 1, 1),
            size=4,
        )
        annotations_builder.draw_text(
            text=text_y,
            position=((x + text_offset_x) / width, (y + text_offset_y_2) / height),
            color=(1, 1, 1, 1),
            size=4,
        )
        annotations_builder.draw_text(
            text=text_z,
            position=((x + text_offset_x) / width, (y + text_offset_y_3) / height),
            color=(1, 1, 1, 1),
            size=4,
        )

        annotations = annotations_builder.build(
            disparity.getTimestamp(), disparity.getSequenceNum()
        )
        self.annotation_output.send(annotations)
        self.passthrough.send(disparity)

    def handle_key_press(self, key: int) -> None:
        if key == -1:
            return
        key_str = chr(key)

        if key_str == "w":
            self._roi.ymin -= self.step
            self._roi.ymax -= self.step
        elif key_str == "a":
            self._roi.xmin -= self.step
            self._roi.xmax -= self.step
        elif key_str == "s":
            self._roi.ymin += self.step
            self._roi.ymax += self.step
        elif key_str == "d":
            self._roi.xmin += self.step
            self._roi.xmax += self.step
        elif key_str == "r":
            self._increase_roi_size()
        elif key_str == "f":
            self._decrease_roi_size()

            self.output_roi.send(self._roi)

    def _increase_roi_size(self):
        if (self._roi.xmax - self._roi.xmin) < 100:
            self._roi.xmin -= 1
            self._roi.xmax += 1
        if (self._roi.ymax - self._roi.ymin) < 100:
            self._roi.ymin -= 1
            self._roi.ymax += 1

    def _decrease_roi_size(self):
        if (self._roi.xmax - self._roi.xmin) > 6:
            self._roi.xmin += 1
            self._roi.xmax -= 1
        if (self._roi.ymax - self._roi.ymin) > 6:
            self._roi.ymin += 1
            self._roi.ymax -= 1
