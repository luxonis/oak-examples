import cv2
import depthai as dai
from depthai_nodes.message import SegmentationMask


class BlurBackground(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()

    def build(
        self,
        input_frame: dai.Node.Output,
        input_mask: dai.Node.Output,
    ) -> "BlurBackground":
        """Link the node input and set the correct source and target image sizes.

        Parameters
        ----------
        input_frame : dai.Node.Output
            The input frame on which the background will be blurred.
        input_mask : dai.Node.Output
            The input segmentation mask that will be used to determine the areas to blur.
            It is assumed persons are class 15 in the mask as that is the default for DeeplabV3+.
        """
        self.link_args(input_frame, input_mask)

        return self

    def process(
        self,
        frame_msg: dai.Buffer,
        mask_msg: dai.Buffer,
    ) -> None:
        """Blurs the background of the input frame based on the segmentation mask."""

        assert isinstance(frame_msg, dai.ImgFrame)
        assert isinstance(mask_msg, SegmentationMask)

        frame = frame_msg.getCvFrame()
        person_mask = (
            mask_msg.mask == 15
        )  # person is class 15 in the output of the model

        bg = frame.copy()
        blurred_bg = cv2.blur(bg, (10, 10))

        blurred_bg[person_mask] = frame[person_mask]

        ts = frame_msg.getTimestamp()
        seq_num = frame_msg.getSequenceNum()

        frame_type = frame_msg.getType()
        img = dai.ImgFrame()
        img.setCvFrame(blurred_bg, frame_type)
        img.setTimestamp(ts)
        img.setSequenceNum(seq_num)

        self.out.send(img)
