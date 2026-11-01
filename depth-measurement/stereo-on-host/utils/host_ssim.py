import depthai as dai
import numpy as np
from depthai_nodes.utils import AnnotationHelper
from skimage.metrics import structural_similarity as ssim


class SSIM(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )
        self.passthrough_disp_generated = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.passthrough_disp_calculated = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self.generated_scale = 8
        self.calculated_scale = 16
        self.max_disparity_pixels = 96

    def build(
        self,
        disp_generated: dai.Node.Output,
        disp_calculated: dai.Node.Output,
        generated_scale: int,
    ) -> "SSIM":
        self.link_args(disp_generated, disp_calculated)
        self.generated_scale = generated_scale
        self.sendProcessingToPipeline(False)
        return self

    def process(self, disp_generated: dai.ImgFrame, disp_calculated: dai.ImgFrame):
        if disp_generated.getSequenceNum() != disp_calculated.getSequenceNum():
            return
        # Both matchers use horizontal pixel disparity, with different fixed-point scales.
        disp1_normalized = (
            np.asarray(disp_generated.getFrame(), dtype=np.float32)
            / self.generated_scale
        )
        disp2_normalized = (
            np.asarray(disp_calculated.getFrame(), dtype=np.float32)
            / self.calculated_scale
        )

        # Note: SSIM calculation is quite slow.
        ssim_noise = ssim(
            disp1_normalized, disp2_normalized, data_range=self.max_disparity_pixels
        )
        annotation_helper = AnnotationHelper()

        annotation_helper.draw_text(
            text=f"SSIM between device and host disparity: {ssim_noise:.4f}",
            position=(0.02, 0.05),
            color=(0, 0, 0, 1),
            background_color=(1, 1, 1, 0.7),
            size=10,
        )

        annotations = annotation_helper.build(
            disp_calculated.getTimestamp(), disp_calculated.getSequenceNum()
        )

        self.output.send(annotations)
        self.passthrough_disp_generated.send(disp_generated)
        self.passthrough_disp_calculated.send(disp_calculated)
