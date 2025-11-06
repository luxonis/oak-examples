from core.model_state import ModelState
from core.snapping.conditions_engine import ConditionsEngine
from core.export.system_state_exporter import SystemStateExporter
from core.services.export_service import ExportService


class ExportServiceManager:
    """
    Facade for the configuration export subsystem.
    """

    def __init__(self, model_state: ModelState, condition_engine: ConditionsEngine):
        self._model_state: ModelState = model_state
        self._condition_engine: ConditionsEngine = condition_engine

        self._exporter: SystemStateExporter = None
        self._service: ExportService = None

    def build(self):
        self._exporter = SystemStateExporter(self._model_state, self._condition_engine)
        self._service = ExportService(self._exporter)

    def register_service(self, visualizer):
        visualizer.registerService(self._service.name, self._service.handle)
