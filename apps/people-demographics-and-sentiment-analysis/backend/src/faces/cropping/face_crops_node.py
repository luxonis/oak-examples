from datetime import timedelta

import depthai as dai
from depthai_nodes.node import FrameCropper, GatherData


class FaceCropsNode(dai.node.ThreadedHostNode):
    """
    High-level node grouping the face-cropping pipeline block:

    preview + face detections
        -> FrameCropper (synchronized face crops)
        -> GatherData (sync crops with reference detections)

    Exposes:
      - out: Face crops for second-stage NNs
      - synced_out: Crops aligned with face detections (for PeopleFacesJoin)
    """

    def __init__(
        self,
        padding: float = 0.0,
        resize_mode: str = "LETTERBOX",
    ) -> None:
        super().__init__()

        self._padding = padding
        self._resize_mode = resize_mode

        self._cropper: FrameCropper = self.createSubnode(FrameCropper)
        self._gather: GatherData = self.createSubnode(GatherData)

        self.out: dai.Node.Output = self._cropper.out
        self.synced_out: dai.Node.Output = self._gather.out

    def build(
        self,
        camera_fps: int,
        preview_source: dai.Node.Output,
        detections_source: dai.Node.Output,
        face_reference_detections: dai.Node.Output,
    ) -> "FaceCropsNode":
        """
        @param camera_fps: The frames per second (FPS) of the camera, used by GatherData.
        @param preview_source: Node output that produces RGB/preview frames (dai.ImgFrame).
        @param detections_source: Node output that produces face detections (ImgDetections)
                                  used to define crop ROIs.
        @param face_reference_detections: Node output that produces face detections (dai.ImgDetections)
                                          used as reference for synchronization in GatherData.
        """
        self._cropper.fromImgDetections(
            inputImgDetections=detections_source,
            outputSize=(300, 300),
            resizeMode=getattr(dai.ImageManipConfig.ResizeMode, self._resize_mode),
            padding=self._padding,
        ).build(inputImage=preview_source)

        self._gather.build(
            cameraFps=camera_fps,
            inputData=self._cropper.out,
            inputReference=face_reference_detections,
            timeout=timedelta(seconds=5 / camera_fps),
            maxPendingFrames=64,
            preserveOrder=True,
        )

        return self

    def run(self) -> None:
        # High-level node: no host-side processing, all logic is in subnodes.
        pass
