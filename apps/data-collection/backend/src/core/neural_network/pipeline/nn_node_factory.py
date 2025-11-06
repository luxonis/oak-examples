import depthai as dai
from config.config_data_classes import NeuralNetworkConfig
from depthai_nodes.node import ParsingNeuralNetwork


class NnNodeFactory:
    """Builds and configures the core ParsingNeuralNetwork node."""

    def __init__(
        self,
        pipeline: dai.Pipeline,
        input_node: dai.Node.Output,
        config: NeuralNetworkConfig,
    ):
        self._pipeline: dai.Pipeline = pipeline
        self._input_node: dai.Node.Output = input_node
        self._config: NeuralNetworkConfig = config

    def build(self) -> ParsingNeuralNetwork:
        backend = self._config.nn_yaml.nn_backend

        nn = self._pipeline.create(ParsingNeuralNetwork)
        nn.setNNArchive(self._config.model.archive)
        nn.setBackend(backend.type)
        nn.setBackendProperties(
            {
                "runtime": backend.runtime,
                "performance_profile": backend.performance_profile,
            }
        )
        nn.setNumInferenceThreads(backend.inference_threads)
        nn.getParser(0).setConfidenceThreshold(backend.confidence_threshold)

        self._input_node.link(nn.inputs["images"])
        return nn
