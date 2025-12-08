import depthai as dai


class NNBuilder:
    """
    Generic 'video -> ImageManip -> NN' branch.

    You pass:
      - model_name: model from the zoo
      - nn_cls:     dai.node.NeuralNetwork OR ParsingNeuralNetwork (wrapper)

    Usage:
      branch = NNBranch(pipeline, platform, "luxonis/fastsam-x:640x352", ParsingNeuralNetwork)
      seg_out = branch.build(video_full)
      fs_w, fs_h = branch.input_size
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        platform: str,
        model_name: str,
        nn_cls,
    ):
        self.pipeline = pipeline
        self.platform = platform
        self.model_name = model_name
        self.nn_cls = nn_cls

        # Load model from zoo
        self.model = dai.NNModelDescription(model_name)
        self.model.platform = platform
        self.archive = dai.NNArchive(dai.getModelFromZoo(self.model))

        # Use generic input size from archive (works for both models)
        w, h = self.archive.getInputSize()
        self.input_width = int(w)
        self.input_height = int(h)

        self.out = None  # will be set in build()

    @property
    def input_size(self) -> tuple[int, int]:
        return self.input_width, self.input_height

    def build(self, video_full: dai.Node.Output) -> dai.Node.Output:
        """
        Wire: video_full -> ImageManip -> NN
        Returns NN output (node.out).
        """
        manip = self.pipeline.create(dai.node.ImageManip)
        manip.initialConfig.setOutputSize(self.input_width, self.input_height)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
        manip.setMaxOutputFrameSize(self.input_width * self.input_height * 3)

        video_full.link(manip.inputImage)

        nn_node = self.pipeline.create(self.nn_cls).build(
            manip.out,
            self.archive,
        )

        self.out = nn_node.out
        return self.out
