from pathlib import Path

from box import Box


class YamlFilesLoader:
    """Loads all YAML configuration files and exposes them as Box objects."""

    def __init__(self, base_dir: Path):
        self._base: Path = base_dir
        self.nn: Box = None
        self.camera: Box = None

    def load_all(self):
        print(f"[YamlConfigManager] Loading from: {self._base.resolve()}")

        def safe_load(name: str, file: str) -> Box:
            path = self._base / file
            if not path.exists():
                raise FileNotFoundError(f"Missing YAML: {path}")
            print(f"[YamlConfigManager] ✓ Loaded {name}: {path.name}")
            return Box.from_yaml(filename=path)

        self.nn = safe_load("nn", "nn.yaml")
        self.camera = safe_load("video", "camera.yaml")
        self.reference_adaptation = safe_load(
            "reference_adaptation", "reference_adaptation.yaml"
        )
