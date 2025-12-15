from pydantic import BaseModel, Field
from typing import Dict, Any, Tuple
import yaml
from pathlib import Path


class PipelineConfig(BaseModel):
    device: str = Field(
        "", description="Device IP, if empty then default device is used"
    )
    output_size: Tuple[int, int] = Field(..., description="(width, height)")
    fps: int = Field(..., description="Frames per second for camera output")


class RoboflowConfig(BaseModel):
    api_key: str = Field(..., description="Roboflow API key")
    workspace: str = Field(..., description="Roboflow workspace name")
    workflow_id: str = Field(..., description="Workflow ID")
    workflow_parameters: Dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    pipeline: PipelineConfig
    roboflow: RoboflowConfig


def load_config(path: str = "yaml_configs/config.yaml"):
    """Loads configuration yaml"""
    config_path = Path(__file__).parent / path
    if config_path is None or not config_path.is_file():
        raise FileNotFoundError(f"Config not found at {config_path}")

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
