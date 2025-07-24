import depthai as dai
import numpy as np
from skimage.metrics import structural_similarity as ssim
from depthai_nodes.utils import AnnotationHelper


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
        self.max_generated_disparity = None
        self.max_calculated_disparity = None

    def setMaxGenDisparity(self, max_generated_disparity):
        self.max_generated_disparity = max_generated_disparity

    def setMaxCalDisparity(self, max_calculated_disparity):
        self.max_calculated_disparity = max_calculated_disparity

    def build(
        self, disp_generated: dai.Node.Output, disp_calculated: dai.Node.Output
    ) -> "SSIM":
        self.link_args(disp_generated, disp_calculated)
        self.sendProcessingToPipeline(False)
        return self

    def process(self, disp_generated: dai.ImgFrame, disp_calculated: dai.ImgFrame):
        if self.max_generated_disparity is None:
            print("Warning: max_generated_disparity not set in SSIM node.")
            return
        if self.max_calculated_disparity is None:
            print("Warning: max_calculated_disparity not set in SSIM node.")
            return

        disp1_subpixel = np.array(disp_generated.getFrame()).astype(np.float32)
        disp1 = disp1_subpixel

        disp2_subpixel = np.array(disp_calculated.getFrame()).astype(np.float32)
        disp2 = disp2_subpixel

        max_disp1 = self.max_generated_disparity
        max_disp2 = self.max_calculated_disparity

        disp1_normalized = disp1 / max_disp1
        disp2_normalized = disp2 / max_disp2

        # Note: SSIM calculation is quite slow.
        ssim_noise = ssim(
            disp1_normalized, disp2_normalized, data_range=1.0, multichannel=False
        )
        annotation_helper = AnnotationHelper()

        annotation_helper.draw_text(
            text=f"SSIM between generated and calculated depth frame: {ssim_noise:.4f}",
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
