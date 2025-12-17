import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork


class NNBuilder:
    """
    Generic 'video -> ImageManip -> NN' branch.
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        platform: str,
        model_name: str,
        nn_cls: type[dai.node.NeuralNetwork] | type[ParsingNeuralNetwork],
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

    @property
    def input_size(self) -> tuple[int, int]:
        return self.input_width, self.input_height

    def build(self, rgb_sensor: dai.Buffer) -> dai.Node.Output:

        nn_node = self.pipeline.create(self.nn_cls).build(
            rgb_sensor,
            self.archive,
        )

        return nn_node.out
