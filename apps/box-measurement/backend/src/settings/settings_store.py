import json
import logging
import os
import threading
from pathlib import Path

from config import STORAGE_BASE_PATH
from settings.settings import Settings

logger = logging.getLogger(__name__)


class SettingsStore:
    _settings: Settings

    def __init__(self):
        self._lock = threading.RLock()
        self._settings_file_path = Path(STORAGE_BASE_PATH) / "settings.json"
        self._load()
        self._persist()

    def get(self) -> Settings:
        with self._lock:
            return self._settings

    def update(self, settings: Settings):
        with self._lock:
            self._settings = settings
            self._persist()

    def _persist(self):
        self._settings_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._settings_file_path, "w") as f:
            f.write(json.dumps(self._settings.model_dump(mode="json")))

    def _load(self):
        if not os.path.exists(self._settings_file_path):
            self._settings = Settings()
            return
        try:
            with open(self._settings_file_path, "r") as f:
                settings = Settings(**json.load(f))
                self._settings = settings
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
            logger.warning("Using default settings")
            self._settings = Settings()
