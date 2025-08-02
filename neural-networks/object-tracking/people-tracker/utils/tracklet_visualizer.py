import depthai as dai
from typing import List

from depthai_nodes.utils import AnnotationHelper


class VisualizedTracklets(dai.Tracklets):
    def __init__(self):
        super().__init__()
        self._labels = None

    def setLabels(self, labels: List[str]):
        self._labels = labels

    def getVisualizationMessage(self):
        annotation_helper = AnnotationHelper()
        for tracklet in self.tracklets:
            if tracklet.status == dai.Tracklet.TrackingStatus.TRACKED:
                annotation_helper.draw_rectangle(
                    top_left=(tracklet.roi.x, tracklet.roi.y),
                    bottom_right=(
                        tracklet.roi.x + tracklet.roi.width,
                        tracklet.roi.y + tracklet.roi.height,
                    ),
                    thickness=2,
                )

                if self._labels:
                    label_txt = self._labels[tracklet.srcImgDetection.label]
                else:
                    label_txt = tracklet.srcImgDetection.label

                annotation_helper.draw_text(
                    text=f"{label_txt} {round(tracklet.srcImgDetection.confidence * 100):<3}% ID: {tracklet.id}",
                    position=(tracklet.roi.x, tracklet.roi.y),
                    size=25,
                )

        annotations = annotation_helper.build(
            timestamp=self.getTimestamp(),
            sequence_num=self.getSequenceNum(),
        )

        return annotations


class TrackletVisualizer(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self._out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.Buffer, True)
            ]
        )

    def build(
        self, tracklets: dai.Node.Output, labels: List[str]
    ) -> "TrackletVisualizer":
        self._labels = labels
        self.link_args(tracklets)
        return self

    def process(self, tracklets: dai.Tracklets) -> None:
        vis_tracklets = VisualizedTracklets()
        vis_tracklets.tracklets = tracklets.tracklets
        vis_tracklets.setLabels(self._labels)
        vis_tracklets.setTimestamp(tracklets.getTimestamp())
        vis_tracklets.setSequenceNum(tracklets.getSequenceNum())
        self._out.send(vis_tracklets)

    @property
    def out(self) -> dai.Node.Output:
        return self._out
