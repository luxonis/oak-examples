from pathlib import Path
from box import Box


class YamlFileLoader:
    """Loads all YAML configuration files and exposes them as Box objects."""

    def __init__(self, base_dir: Path):
        self._base: Path = base_dir

    def load(self, filename: str) -> Box:
        path = self._base / filename

        if not path.exists():
            raise FileNotFoundError(f"Missing YAML config: {path}")

        print(f"[YamlConfig] Loaded: {path.name}")
        return Box.from_yaml(filename=path)
