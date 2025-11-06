from pathlib import Path
from dataclasses import dataclass
import depthai as dai
from box import Box


@dataclass
class ModelInfo:
    """Stores paths and dimensions of the detection model."""

    yaml_path: Path
    width: int
    height: int
    description: dai.NNModelDescription
    archive: dai.NNArchive
    precision: str


@dataclass
class VideoConfig:
    """Stores video configuration (resolution, FPS)."""

    resolution: list[int]
    fps: int
    media_path: str
    width: int
    height: int


@dataclass
class NeuralNetworkConfig:
    """Stores neural network configuration (confidence thresholds, etc.)."""

    nn_yaml: Box
    model: ModelInfo
