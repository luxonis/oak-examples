from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Optional
from box import Box

from config.cli_env_loader import CLIEnvLoader
from config.yaml_config_manager import YamlConfigManager
from config.model_loader import ModelLoader
from config.config_data_classes import ModelInfo, VideoConfig, NeuralNetworkConfig


class SystemConfiguration:
    """
    Class that manages configuration initialization.
    """

    def __init__(self, platform: str):
        self._platform: str = platform
        self._args: Namespace = None
        self._yaml: Optional[YamlConfigManager] = None
        self._model_info: Optional[ModelInfo] = None

    def build(self):
        """Initialize all configuration subsystems."""
        self._args = CLIEnvLoader.parse_arguments()

        base = Path(__file__).parent / "yaml_configs"

        self._yaml = YamlConfigManager(base)
        self._yaml.load_all()

        model_loader = ModelLoader(self._platform, self._args)
        self._model_info = model_loader.load_model_info()
        self._model_info.precision = self._yaml.prompts.precision

    def get_video_config(self) -> VideoConfig:
        if self._args.fps_limit is None:
            self._args.fps_limit = self._yaml.video.default_fps
            print(f"\nFPS limit set to {self._args.fps_limit} for {self._platform}\n")

        return VideoConfig(
            resolution=self._yaml.video.video_resolution,
            fps=self._args.fps_limit,
            media_path=self._args.media_path,
            width=self._model_info.width,
            height=self._model_info.height,
        )

    def get_neural_network_config(self) -> NeuralNetworkConfig:
        return NeuralNetworkConfig(
            nn_yaml=self._yaml.nn,
            model=self._model_info,
        )

    def get_snaps_config(self) -> Box:
        return self._yaml.conditions

    def get_prompts_config(self) -> Box:
        return self._yaml.prompts
