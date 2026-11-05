"""Service schemas for recent events and their temporary capture files."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from events.event_store import DangerEventType, EventStore


class GetEventsRequest(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int | None = Field(None, gt=0)


class EventFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    path: str


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    triggered_at: datetime
    frame_timestamp_seconds: float
    event_type: DangerEventType
    files: list[EventFileResponse]


class GetEventsResponse(BaseModel):
    events: list[EventResponse]
    total_count: int


class GetEventFileRequest(BaseModel):
    path: str = Field(min_length=1)


def get_events(store: EventStore, request: GetEventsRequest) -> GetEventsResponse:
    """Return a newest-first page of retained events and the full count."""
    events, count = store.list(request.offset, request.limit)
    return GetEventsResponse(
        events=[EventResponse.model_validate(event) for event in events],
        total_count=count,
    )
