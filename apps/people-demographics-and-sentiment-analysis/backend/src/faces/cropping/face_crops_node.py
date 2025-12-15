import depthai as dai
from typing import Optional

from depthai_nodes.node import GatherData
from depthai_nodes.node.utils import generate_script_content


class FaceCropsNode(dai.node.ThreadedHostNode):
    """
    High-level node grouping the face-cropping pipeline block:

    preview + face detections
        -> Script (crop ROIs, cfg)
        -> ImageManip (apply cfg, output crops)
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

        self._camera_fps: Optional[int] = None
        self._padding = padding
        self._resize_mode = resize_mode

        self._script: dai.node.Script = self.createSubnode(dai.node.Script)
        self._img_manip: dai.node.ImageManip = self.createSubnode(dai.node.ImageManip)
        self._gather: GatherData = self.createSubnode(GatherData)

        self.preview: dai.Node.Input = self._script.inputs["preview"]
        self.detections: dai.Node.Input = self._script.inputs["det_in"]

        self.out: dai.Node.Output = self._img_manip.out
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
        @param face_reference_detections: Node output that produces face detections (ImgDetectionsExtended)
                                          used as reference for synchronization in GatherData.
        """
        self._camera_fps = camera_fps

        script_code = generate_script_content(
            resize_height=300,
            resize_width=300,
            resize_mode=self._resize_mode,
            padding=self._padding,
        )
        self._script.setScript(script_code)

        preview_source.link(self.preview)
        detections_source.link(self.detections)

        self._img_manip.inputConfig.setWaitForMessage(True)
        self._img_manip.inputImage.setBlocking(True)

        self._script.outputs["manip_img"].link(self._img_manip.inputImage)
        self._script.outputs["manip_cfg"].link(self._img_manip.inputConfig)

        self._gather.build(
            camera_fps=self._camera_fps,
            input_data=self._img_manip.out,
            input_reference=face_reference_detections,
        )

        return self

    def run(self) -> None:
        # High-level node: no host-side processing, all logic is in subnodes.
        pass
