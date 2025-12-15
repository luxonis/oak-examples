import depthai as dai


class NNArchiveLoader:
    """
    Helper class to fetch and load model archives for the pipeline.
    """

    def __init__(self, platform: str):
        self._platform = platform

    def load(self, model_name: str) -> dai.NNArchive:
        """
        Loads model from DepthAI Zoo and returns the archive.
        """
        description = dai.NNModelDescription(model=model_name, platform=self._platform)
        return dai.NNArchive(dai.getModelFromZoo(description))
