import depthai as dai
from pydantic import BaseModel, ConfigDict

from api.request_handler import EmptyBody, add_request_handler
from services.event_export.coordinator import EventExportCoordinator
from services.event_export.types import EventExportState


class LogExportWarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    suggested_action: str
    file: str | None = None


class EventArchiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    host_path: str
    byte_size: int
    event_count: int
    created_at: str
    scp_command: str
    warnings: list[LogExportWarningResponse]


class EventExportStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: EventExportState
    archive: EventArchiveResponse | None
    processed_event_count: int
    total_event_count: int
    failure_message: str | None


class EventExportRequestHandler:
    def __init__(
        self,
        coordinator: EventExportCoordinator,
        visualizer: dai.RemoteConnection,
    ) -> None:
        self._coordinator = coordinator
        add_request_handler(
            visualizer, "getEventExportStatus", self.get_event_export_status
        )
        add_request_handler(visualizer, "createEventExport", self.create_event_export)
        add_request_handler(visualizer, "deleteEventExport", self.delete_event_export)

    def get_event_export_status(
        self, request: EmptyBody
    ) -> EventExportStatusResponse:
        return EventExportStatusResponse.model_validate(self._coordinator.get_status())

    def create_event_export(self, request: EmptyBody) -> EventExportStatusResponse:
        return EventExportStatusResponse.model_validate(
            self._coordinator.create_archive()
        )

    def delete_event_export(self, request: EmptyBody) -> EventExportStatusResponse:
        return EventExportStatusResponse.model_validate(
            self._coordinator.delete_archive()
        )
