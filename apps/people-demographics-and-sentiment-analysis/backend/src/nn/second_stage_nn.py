import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork, GatherData


class SecondStageNNNode(dai.node.ThreadedHostNode):
    """
    High-level node for a second-stage neural network block.

    Receives detection crops from the first stage and runs them through:
        -> ImageManip (resize to NN input resolution);
        -> ParsingNeuralNetwork (run the model);
        -> GatherData (synchronize NN outputs with the correct reference detections).

    Exposes:
      - synced_out: NN outputs aligned with reference detections (for PeopleJoinNode)
    """

    def __init__(self, multi_head_nn: bool = False) -> None:
        """
        @param multi_head_nn: Set True if the model outputs multiple layers (e.g., Age+Gender),
                              False for single output (e.g., Emotion, ReID).
        """
        super().__init__()

        self._multi_head_nn = multi_head_nn

        self._img_manip: dai.node.ImageManip = self.createSubnode(dai.node.ImageManip)
        self._nn: ParsingNeuralNetwork = self.createSubnode(ParsingNeuralNetwork)
        self._gather: GatherData = self.createSubnode(GatherData)

        self.synced_out: dai.Node.Output = self._gather.out

    def build(
        self,
        image_source: dai.Node.Output,
        archive: dai.NNArchive,
        reference_detections: dai.Node.Output,
        camera_fps: int,
    ) -> "SecondStageNNNode":
        """
        @param image_source: Source RGB frames.
        @param archive: NN archive providing the model and input resolution.
        @param reference_detections: Detections from the first-stage NN model, used by GatherData to sync
                                     NN outputs to the correct detections.
        @param camera_fps: Camera FPS.
        """
        model_w = archive.getInputWidth()
        model_h = archive.getInputHeight()

        self._img_manip.initialConfig.setOutputSize(model_w, model_h)
        self._img_manip.inputImage.setBlocking(True)
        self._img_manip.setMaxOutputFrameSize(model_w * model_h * 3)
        image_source.link(self._img_manip.inputImage)

        self._nn.build(self._img_manip.out, archive)

        self._gather.build(
            camera_fps=camera_fps,
            input_data=self._nn.outputs if self._multi_head_nn else self._nn.out,
            input_reference=reference_detections,
        )

        return self

    def run(self) -> None:
        # High-level node: no host-side processing, subnodes do all the work.
        pass
