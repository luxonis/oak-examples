import depthai as dai


class NNBuilder:
    """
    Generic 'video -> ImageManip -> NN' branch.
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

        self.model = dai.NNModelDescription(model_name)
        self.model.platform = platform
        self.archive = dai.NNArchive(dai.getModelFromZoo(self.model))

        w, h = self.archive.getInputSize()
        self.input_width = int(w)
        self.input_height = int(h)

        self.out = None

    @property
    def input_size(self) -> tuple[int, int]:
        return self.input_width, self.input_height

    def build(self, video_full: dai.Node.Output) -> dai.Node.Output:
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
