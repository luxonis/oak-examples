import depthai as dai
import numpy as np
from depthai_nodes.node import ParsingNeuralNetwork


def convert_disparity(disparity_px, baseline_mm, focal_length_px):
    """Match NeuralDepth: RAW16 disparity (pixels * 16), RAW16 depth (mm)."""
    disparity_px = np.asarray(disparity_px, dtype=np.float64)
    valid = np.isfinite(disparity_px) & (disparity_px > 0)
    disparity = np.zeros(disparity_px.shape, dtype=np.uint16)
    depth = np.zeros(disparity_px.shape, dtype=np.uint16)
    disparity[valid] = np.rint(np.minimum(disparity_px[valid], 65535 / 16) * 16).astype(
        np.uint16
    )
    # Compute from the original floating-point disparity, before quantization.
    with np.errstate(over="ignore", divide="ignore"):
        depth[valid] = np.clip(
            baseline_mm * focal_length_px / disparity_px[valid], 0, 65535
        ).astype(np.uint16)
    return disparity, depth


def make_frame(data, reference, result):
    frame = dai.ImgFrame()
    frame.setFrame(data)
    frame.setType(dai.ImgFrame.Type.RAW16)
    frame.setTransformation(reference.getTransformation())
    frame.setWidth(data.shape[1])
    frame.setHeight(data.shape[0])
    frame.setInstanceNum(reference.getInstanceNum())
    frame.setBufferMetadataFrom(result)
    return frame


class LAS2Output(dai.node.HostNode):
    """Adapt LAS2's Map2D using the actual rectified-left camera geometry."""

    def __init__(self):
        super().__init__()
        self.disparity = self.createOutput()
        self.depth = self.createOutput()
        for output in (self.disparity, self.depth):
            output.setPossibleDatatypes([(dai.DatatypeEnum.ImgFrame, True)])

    def build(self, disparity, reference, calibration):
        translation = calibration.getCameraTranslationVector(
            dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C, False
        )
        # Same calibrated baseline convention used by native NeuralDepth.
        self.axis = 0 if abs(translation[0]) >= abs(translation[1]) else 1
        self.baseline_mm = abs(translation[self.axis]) * 10
        if not np.isfinite(self.baseline_mm) or self.baseline_mm <= 0:
            raise ValueError("LAS2 requires a calibrated stereo baseline")
        self.link_args(disparity, reference)
        return self

    def process(self, result: dai.Buffer, reference: dai.Buffer):
        if not isinstance(result, dai.beta.Map2D):
            raise TypeError("LAS2 parser must emit Map2D disparity")
        if not isinstance(reference, dai.ImgFrame):
            raise TypeError("LAS2 left passthrough must emit ImgFrame")
        disparity_px = result.getMap()
        if disparity_px.shape != (reference.getHeight(), reference.getWidth()):
            raise ValueError("LAS2 disparity must match the rectified input resolution")
        intrinsics = reference.getTransformation().getIntrinsicMatrix()
        focal_length_px = intrinsics[self.axis][self.axis]
        disparity, depth = convert_disparity(
            disparity_px, self.baseline_mm, focal_length_px
        )
        self.disparity.send(make_frame(disparity, reference, result))
        self.depth.send(make_frame(depth, reference, result))


def build_las2(pipeline, left, right, model, calibration):
    archive = dai.NNArchive(
        dai.getModelFromZoo(
            dai.NNModelDescription(
                f"luxonis/lite-any-stereo-v2:{model}", platform="RVC4"
            )
        )
    )
    # Use the same synchronized rectification path as native NeuralDepth.
    sync = pipeline.create(dai.node.Sync)
    left.link(sync.inputs["left"])
    right.link(sync.inputs["right"])
    demux = pipeline.create(dai.node.MessageDemux)
    sync.out.link(demux.input)
    rectification = pipeline.create(dai.node.Rectification)
    rectification.setOutputSize(archive.getInputSize())
    demux.outputs["left"].link(rectification.input1)
    demux.outputs["right"].link(rectification.input2)

    nn = pipeline.create(ParsingNeuralNetwork)
    nn.setNNArchive(archive)
    for name, output in (
        ("left", rectification.output1),
        ("right", rectification.output2),
    ):
        nn.inputs[name].setBlocking(True)
        nn.inputs[name].setMaxSize(4)
        output.link(nn.inputs[name])

    return pipeline.create(LAS2Output).build(
        nn.out, nn.passthroughs["left"], calibration
    )
