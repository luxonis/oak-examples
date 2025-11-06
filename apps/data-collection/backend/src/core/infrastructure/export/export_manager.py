from core.model_state import ModelState
from core.snapping.conditions_engine import ConditionsEngine
from config.system_state_exporter import SystemStateExporter
from core.services.export_service import ExportService


class ExportManager:
    """
    Facade for the configuration export subsystem.

    Responsibilities:
      • Build SystemStateExporter
      • Create GetConfigService exposing export API
    """

    def __init__(self, model_state: ModelState, condition_engine: ConditionsEngine):
        self._model_state = model_state
        self._condition_engine = condition_engine

        self._exporter: SystemStateExporter = None
        self._service: ExportService = None
        self._build()

    def _build(self):
        self._exporter = SystemStateExporter(self._model_state, self._condition_engine)
        self._service = ExportService(self._exporter)

    def get_service(self) -> ExportService:
        return self._service
