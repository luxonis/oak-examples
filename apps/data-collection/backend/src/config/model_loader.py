from argparse import Namespace

import depthai as dai
from pathlib import Path
from config.config_data_classes import ModelInfo


class ModelLoader:
    """Resolves DepthAI model archive and metadata."""

    def __init__(self, platform: str, args):
        self.platform: str = platform
        self.args: Namespace = args

    def load_model_info(self) -> ModelInfo:
        models_dir = Path(__file__).parent.parent / "depthai_models"
        yaml_file = f"yoloe_v8_l_fp16.{self.platform}.yaml"
        yaml_path = models_dir / yaml_file

        if not yaml_path.exists():
            raise SystemExit(f"Model YAML not found for yoloe: {yaml_path}")

        desc = dai.NNModelDescription.fromYamlFile(str(yaml_path))
        desc.platform = self.platform
        archive = dai.NNArchive(dai.getModelFromZoo(desc))
        width, height = archive.getInputSize()

        return ModelInfo(
            yaml_path=yaml_path,
            width=width,
            height=height,
            description=desc,
            archive=archive,
            precision="",
        )
