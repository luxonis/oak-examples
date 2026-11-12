"""Box measurement from color and a point cloud, composed of detection and dimensioning."""

import depthai as dai
from depthai_nodes.node import BaseThreadedHostNode

from solutions_sdk.box_measurement.message import SupportPlane
from solutions_sdk.box_measurement.node.detection import BoxDetector
from solutions_sdk.box_measurement.node.dimensioning import BoxDimensioner


class BoxMeasurer(BaseThreadedHostNode):
    """Measure boxes from color and an organized millimeter point cloud.

    Wires a ``BoxDetector`` into a ``BoxDimensioner``. ``out`` emits one
    measurement observation per box detection, with aggregated dimensions,
    measured against the active support plane. Color and cloud must cover the
    same field of view; their resolutions may differ. The plane can come from
    any source; no calibration node is required.
    """

    def __init__(self) -> None:
        try:
            super().__init__()
        except AttributeError:
            # The depthai-nodes base reads the default device's platform.
            if self.getParentPipeline().getDefaultDevice() is not None:
                raise
            raise ValueError("BoxMeasurer currently requires an RVC4 device") from None
        self._detector = self.createSubnode(BoxDetector)
        self._dimensioner = self.createSubnode(BoxDimensioner)

    def build(
        self,
        color: dai.Node.Output,
        point_cloud: dai.Node.Output,
        point_cloud_size: tuple[int, int],
        support_plane: SupportPlane | None = None,
        confidence_threshold: float = 0.5,
    ) -> "BoxMeasurer":
        # The dimensioner validates the cloud size before the detector fetches
        # the model.
        self._dimensioner.build(
            self._detector.out, point_cloud, point_cloud_size, support_plane
        )
        self._detector.build(color, confidence_threshold)
        return self

    @property
    def out(self) -> dai.Node.Output:
        return self._dimensioner.out

    @property
    def box_cloud_out(self) -> dai.Node.Output:
        return self._dimensioner.box_cloud_out

    def setSupportPlane(self, plane: SupportPlane) -> None:
        self._dimensioner.setSupportPlane(plane)

    def getSupportPlane(self) -> SupportPlane | None:
        return self._dimensioner.getSupportPlane()

    def clearSupportPlane(self) -> None:
        self._dimensioner.clearSupportPlane()

    def setConfidenceThreshold(self, threshold: float) -> None:
        """Change the detection confidence threshold live; raises before build."""
        self._detector.setConfidenceThreshold(threshold)

    def run(self) -> None:
        return
