import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsBridge
from .filter_n_largest_bboxes import FilterNLargestBBoxes


class FaceDetectionNode(dai.node.ThreadedHostNode):
    """
    High-level node grouping the face detection pipeline block:
        ImageManip -> ParsingNeuralNetwork -> FilterNLargestBBoxes -> ImgDetectionsBridge

    Acts as a structural container (NodeGroup); it only creates and wires subnodes and
    does not process messages at runtime.
    """

    def __init__(self, max_faces: int = 3) -> None:
        super().__init__()
        self._max_faces = max_faces

        self._img_manip: dai.node.ImageManip = self.createSubnode(dai.node.ImageManip)
        self._nn: ParsingNeuralNetwork = self.createSubnode(ParsingNeuralNetwork)
        self._filtered_face_det: FilterNLargestBBoxes = self.createSubnode(
            FilterNLargestBBoxes
        )
        self._filtered_face_det_bridge: ImgDetectionsBridge = self.createSubnode(
            ImgDetectionsBridge
        )

        self.inputImage: dai.Node.Input = self._img_manip.inputImage
        self.filtered_output: dai.Node.Output = self._filtered_face_det.out
        self.filtered_bridge_output: dai.Node.Output = (
            self._filtered_face_det_bridge.out
        )

    def build(
        self, image_source: dai.Node.Output, archive: dai.NNArchive
    ) -> "FaceDetectionNode":
        model_w = archive.getInputWidth()
        model_h = archive.getInputHeight()

        self._img_manip.initialConfig.setOutputSize(model_w, model_h)
        self._img_manip.initialConfig.setReusePreviousImage(False)
        self._img_manip.inputImage.setBlocking(True)
        image_source.link(self.inputImage)

        self._nn.build(self._img_manip.out, archive)
        self._nn.getParser().setConfidenceThreshold(0.85)
        self._nn.getParser().setIOUThreshold(0.75)

        self._filtered_face_det.build(
            face_detections=self._nn.out,
            n_face_crops=self._max_faces,
        )
        self._filtered_face_det_bridge.build(self._filtered_face_det.out)

        return self

    def run(self):
        # High-level node: no host-side processing, subnodes run on device.
        pass
