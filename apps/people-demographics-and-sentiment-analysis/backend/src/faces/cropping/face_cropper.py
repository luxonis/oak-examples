import depthai as dai
from typing import Optional, List

from depthai_nodes.node.utils import generate_script_content


class FaceCropper:
    """
    Helper class that:
    - takes preview frames and face detections;
    - uses Script node + ImageManip node to generate face crops;
    - emits face crops for second-stage NNs.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        preview_source: dai.Node.Output,
        detections_source: dai.Node.Output,
        padding: float = 0.0,
        resize_mode: str = "LETTERBOX",
        valid_labels: Optional[List[int]] = None,
    ):
        self._pipeline = pipeline
        self._preview_source = preview_source
        self._detections_source = detections_source
        self._padding = padding
        self._resize_mode = resize_mode
        self._valid_labels = valid_labels

        self._script: Optional[dai.node.Script] = None
        self._img_manip: Optional[dai.node.ImageManip] = None

    def build(self) -> "FaceCropper":
        self._script = self._pipeline.create(dai.node.Script)

        script_code = generate_script_content(
            resize_height=300,
            resize_width=300,
            resize_mode=self._resize_mode,
            padding=self._padding,
            valid_labels=self._valid_labels,
        )
        self._script.setScript(script_code)

        self._preview_source.link(self._script.inputs["preview"])
        self._detections_source.link(self._script.inputs["det_in"])

        self._img_manip = self._create_image_manip()

        self._script.outputs["manip_img"].link(self._img_manip.inputImage)
        self._script.outputs["manip_cfg"].link(self._img_manip.inputConfig)

        return self

    def _create_image_manip(self) -> dai.node.ImageManip:
        img_manip = self._pipeline.create(dai.node.ImageManip)
        img_manip.inputConfig.setWaitForMessage(True)
        img_manip.inputImage.setBlocking(True)
        return img_manip

    @property
    def crops_out(self) -> dai.Node.Output:
        """Cropped faces for second-stage NNs."""
        return self._img_manip.out
