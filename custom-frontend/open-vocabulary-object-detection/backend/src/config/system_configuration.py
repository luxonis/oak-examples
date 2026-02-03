from dataclasses import dataclass
from pathlib import Path
from argparse import Namespace
import logging

from box import Box
import depthai as dai

from .config_data_classes import ModelInfo, VideoConfig, NeuralNetworkConfig

log = logging.getLogger(__name__)

DETECTOR_YAMLS = {
    "yolo-world": {"fp16": "yolo_world_l_fp16", "int8": "yolo_world_l"},
    "yoloe": {"fp16": "yoloe_v8_l_fp16"},
}


@dataclass
class SystemConfig:
    video: VideoConfig
    nn: NeuralNetworkConfig


def build_configuration(platform: str, args: Namespace) -> SystemConfig:
    """From CLI args if provided, if not use config.yaml defaults."""
    configs_dir = Path(__file__).parent
    yamls_dir = configs_dir / "yaml_configs"

    yaml_config = _load_yaml_config(yamls_dir / "config.yaml")

    model_name = (getattr(args, "model", None) or yaml_config.model.name).lower()
    precision = yaml_config.model.precision

    prompts_file = yaml_config.model.prompts_files.get(model_name)
    if not prompts_file:
        raise ValueError(f"No prompts config registered for model '{model_name}'.")

    prompts_path = yamls_dir / prompts_file
    if not prompts_path.exists():
        raise FileNotFoundError(f"Prompts config not found: {prompts_path}")
    prompts = Box.from_yaml(filename=prompts_path)

    model_info = _load_model(platform, precision, model_name)

    # Video config
    fps = getattr(args, "fps_limit", None) or yaml_config.video.fps
    video = VideoConfig(
        fps=fps,
        media_path=getattr(args, "media_path", None),
        width=int(yaml_config.video.width),
        height=int(yaml_config.video.height),
    )

    # NN config
    b = yaml_config.nn.backend
    nn = NeuralNetworkConfig(
        model=model_info,
        backend_type=str(b.type),
        runtime=str(b.runtime),
        performance_profile=str(b.performance_profile),
        num_inference_threads=int(b.inference_threads),
        confidence_thr=float(yaml_config.nn.confidence_thr),
        prompts=prompts,
    )

    return SystemConfig(video=video, nn=nn)


def _load_yaml_config(path: Path) -> Box:
    if not path.exists():
        raise FileNotFoundError(f"Missing root config: {path}")
    return Box.from_yaml(filename=path)


def _load_model(platform: str, precision: str, model_name: str) -> ModelInfo:
    models_dir = Path(__file__).parent.parent / "depthai_models"

    if model_name not in DETECTOR_YAMLS:
        raise ValueError(
            f"Unknown model: {model_name}. Choose from: {list(DETECTOR_YAMLS)}"
        )

    yaml_base = DETECTOR_YAMLS[model_name].get(precision)
    if not yaml_base:
        supported = list(DETECTOR_YAMLS[model_name].keys())
        raise ValueError(
            f"Model '{model_name}' does not support precision '{precision}'. "
            f"Supported: {supported}."
        )

    yaml_path = models_dir / f"{yaml_base}.{platform}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Model YAML not found: {yaml_path}")

    desc = dai.NNModelDescription.fromYamlFile(str(yaml_path))
    desc.platform = platform
    archive = dai.NNArchive(dai.getModelFromZoo(desc))
    w, h = archive.getInputSize()
    log.info(f"Loaded model '{model_name}' ({precision}) from {yaml_path.name}")

    return ModelInfo(
        name=model_name,
        precision=precision,
        yaml_path=yaml_path,
        width=w,
        height=h,
        description=desc,
        archive=archive,
    )
