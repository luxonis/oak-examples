import depthai as dai
import numpy as np

from .visualizer_utils import xfeat_visualizer


def _visualization_frame(pixels: np.ndarray, source: dai.ImgFrame) -> dai.ImgFrame:
    """Wrap a visualization, keeping the timing of the frame it was drawn from."""
    frame = dai.ImgFrame()
    frame.setCvFrame(pixels, dai.ImgFrame.Type.BGR888i)
    frame.setBufferMetadataFrom(source)
    if pixels.shape[:2] == (source.getHeight(), source.getWidth()):
        # Fallback: the source frame passed through unchanged.
        frame.setTransformation(source.getTransformation())
    else:
        # Side-by-side match mosaic; describe it as its own image space.
        frame.setTransformation(dai.ImgTransformation(pixels.shape[1], pixels.shape[0]))
    return frame


class StereoVersionVisualizer(dai.node.HostNode):
    """
    Custom node for creating visualizations for stereo mode.
    It visualizes both frame and draw lines between matched features and returns the dai.ImgFrame.
    """

    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(
        self,
        left_frame_input: dai.Node.Output,
        right_frame_input: dai.Node.Output,
        tracked_features: dai.Node.Output,
    ) -> "StereoVersionVisualizer":
        self.link_args(left_frame_input, right_frame_input, tracked_features)
        return self

    def process(
        self,
        left_frame: dai.Buffer,
        right_frame: dai.Buffer,
        tracked_features: dai.Buffer,
    ) -> None:
        assert isinstance(left_frame, dai.ImgFrame)
        assert isinstance(right_frame, dai.ImgFrame)
        assert isinstance(tracked_features, dai.TrackedFeatures)

        resulting_frame = xfeat_visualizer(
            left_frame.getCvFrame(),
            right_frame.getCvFrame(),
            tracked_features.trackedFeatures,
            draw_warp_corners=False,
        )

        self.output.send(_visualization_frame(resulting_frame, right_frame))


class MonoVersionVisualizer(dai.node.HostNode):
    """
    Custom node for creating visualizations for mono mode.
    It visualizes both frame and draw lines between matched features and returns the dai.ImgFrame.
    """

    def __init__(self) -> None:
        super().__init__()
        self.referece_frame = None
        self.set_reference_frame = False
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def setReferenceFrame(self) -> None:
        self.set_reference_frame = True

    def build(
        self, target_frame_input: dai.Node.Output, tracked_features: dai.Node.Output
    ) -> "MonoVersionVisualizer":
        self.link_args(target_frame_input, tracked_features)
        return self

    def process(self, target_frame: dai.Buffer, tracked_features: dai.Buffer) -> None:
        assert isinstance(target_frame, dai.ImgFrame)
        assert isinstance(tracked_features, dai.TrackedFeatures)

        target_image = target_frame.getCvFrame()

        if self.set_reference_frame:
            self.referece_frame = target_image
            self.set_reference_frame = False

        if self.referece_frame is not None:
            resulting_frame = xfeat_visualizer(
                self.referece_frame, target_image, tracked_features.trackedFeatures
            )

        else:
            resulting_frame = target_image

        self.output.send(_visualization_frame(resulting_frame, target_frame))
