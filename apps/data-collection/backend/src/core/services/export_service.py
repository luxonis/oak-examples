from core.services.base_service import BaseService
from config.system_state_exporter import SystemStateExporter
from core.services.service_name import ServiceName


class ExportService(BaseService[None]):
    """Returns the current configuration state to the frontend."""

    NAME = ServiceName.EXPORT

    def __init__(self, config_exporter: SystemStateExporter):
        super().__init__()
        self.config_exporter = config_exporter

    def handle(self, payload: None = None) -> dict[str, any]:
        try:
            config = self.config_exporter.export_config()
            print("[ExportService] returning:", config)
            return config
        except Exception as e:
            print("[ExportService] ERROR:", e)
            raise
