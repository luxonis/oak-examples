import depthai as dai


class PinholeView(dai.node.HostNode):
    """Describes an undistorted camera frame as a plain pinhole camera of its own size.

    Workaround for depthai 3.12: ImgTransformation.getDstMaskPt reports most of a
    downscaled camera output as outside the image, so Stitching in PLANAR_PROJECTION
    mode finds no input that sees the plane. An undistorted frame is exactly a pinhole
    image, so replacing its transformation loses nothing: the intrinsics of the output
    and the extrinsics are kept.
    """

    def __init__(self) -> None:
        super().__init__()
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, undistorted_frames: dai.Node.Output) -> "PinholeView":
        self.link_args(undistorted_frames)
        return self

    def process(self, frame: dai.ImgFrame) -> None:
        transformation = frame.getTransformation()
        width, height = transformation.getSize()
        frame.setTransformation(
            dai.ImgTransformation(
                width,
                height,
                transformation.getIntrinsicMatrix(),
                dai.CameraModel.Perspective,
                [],
                transformation.getExtrinsics(),
            )
        )
        self.output.send(frame)
