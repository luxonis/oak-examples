import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from database.connection import DbSession
from database.models.event import MeasurementEventType
from database.repositories.event_repository import EventRepository
from util.event_files import resolve_event_file_path

logger = logging.getLogger(__name__)


class GetEventsRequest(BaseModel):
    from_time: datetime | None = None
    to_time: datetime | None = None
    offset: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, gt=0)

    @field_validator("to_time")
    @classmethod
    def validate_time_range(
        cls, value: datetime | None, info: ValidationInfo
    ) -> datetime | None:
        from_time = info.data.get("from_time")
        if value is not None and from_time is not None and from_time > value:
            raise ValueError("from_time must be less than or equal to to_time")

        return value


class EventFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    path: str


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    event_type: MeasurementEventType
    track_id: int
    length_mm: float | None
    width_mm: float | None
    height_mm: float | None
    volume_mm3: float | None
    files: list[EventFileResponse]

    @field_validator("created_at")
    @classmethod
    def normalize_created_at_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)


class GetEventsResponse(BaseModel):
    events: list[EventResponse]
    total_count: int


class GetEventFileRequest(BaseModel):
    path: str = Field(min_length=1)


class DeleteEventRequest(BaseModel):
    id: int


class DeleteEventResponse(BaseModel):
    deleted: bool


def get_events(request: GetEventsRequest) -> GetEventsResponse:
    with DbSession() as session:
        repository = EventRepository(session)
        events = repository.get(
            from_time=request.from_time,
            to_time=request.to_time,
            offset=request.offset,
            limit=request.limit,
        )
        total_count = repository.count(
            from_time=request.from_time,
            to_time=request.to_time,
        )

    return GetEventsResponse(
        events=[EventResponse.model_validate(event) for event in events],
        total_count=total_count,
    )


def get_event_file(request: GetEventFileRequest) -> bytes | None:
    try:
        return resolve_event_file_path(request.path).read_bytes()
    except FileNotFoundError:
        logger.warning("Event file is unavailable: %s", request.path)
        return None
    except OSError:
        logger.exception("Error reading event file %s", request.path)
        return None


def delete_event(request: DeleteEventRequest) -> DeleteEventResponse:
    with DbSession() as session:
        deleted = EventRepository(session).delete(request.id)

    if deleted:
        logger.info("Deleted measurement event %s", request.id)
    else:
        logger.warning("Measurement event %s not found for deletion", request.id)

    return DeleteEventResponse(deleted=deleted)
