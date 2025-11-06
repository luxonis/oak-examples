from pathlib import Path
from box import Box


class YamlConfigManager:
    """Loads all YAML configuration files and exposes them as Box objects."""

    def __init__(self, base_dir: Path):
        self._base = base_dir
        self.nn: Box | None = None
        self.video: Box | None = None
        self.conditions: Box | None = None
        self.prompts: Box | None = None

    def load_all(self) -> None:
        """Load all YAML configs from the given base directory."""
        print(f"[YamlConfigManager] Loading from: {self._base.resolve()}")

        def safe_load(name: str, file: str) -> Box:
            path = self._base / file
            if not path.exists():
                raise FileNotFoundError(f"Missing YAML: {path}")
            print(f"[YamlConfigManager] ✓ Loaded {name}: {path.name}")
            return Box.from_yaml(filename=path)

        self.nn = safe_load("nn", "nn_config.yaml")
        self.video = safe_load("video", "visual_constants.yaml")
        self.conditions = safe_load("conditions", "conditions.yaml")
        self.prompts = safe_load("prompts", "prompts_config.yaml")
