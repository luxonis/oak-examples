from dataclasses import dataclass, field
from datetime import datetime
import logging

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from database.models.event import (
    MeasurementEvent,
    MeasurementEventFile,
    MeasurementEventType,
)
from util.event_files import resolve_event_file_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeasurementEventFileData:
    name: str
    path: str


@dataclass
class MeasurementEventData:
    created_at: datetime
    event_type: MeasurementEventType
    track_id: int
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    volume_mm3: float | None = None
    files: list[MeasurementEventFileData] = field(default_factory=list)


class EventRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, event: MeasurementEventData) -> int:
        """Persist the event and return its database id."""
        db_event = MeasurementEvent(
            created_at=event.created_at,
            event_type=event.event_type,
            track_id=event.track_id,
            length_mm=event.length_mm,
            width_mm=event.width_mm,
            height_mm=event.height_mm,
            volume_mm3=event.volume_mm3,
            files=[
                MeasurementEventFile(name=saved_file.name, path=saved_file.path)
                for saved_file in event.files
            ],
        )
        self._session.add(db_event)
        self._session.commit()
        return db_event.id

    def update_dimensions(
        self,
        event_id: int,
        *,
        length_mm: float,
        width_mm: float,
        height_mm: float,
        volume_mm3: float,
    ) -> bool:
        event = self._session.get(MeasurementEvent, event_id)
        if event is None:
            return False

        event.length_mm = length_mm
        event.width_mm = width_mm
        event.height_mm = height_mm
        event.volume_mm3 = volume_mm3
        self._session.commit()
        return True

    def get(
        self,
        *,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[MeasurementEvent]:
        statement = self._events_newest_first()

        if from_time is not None:
            statement = statement.where(MeasurementEvent.created_at >= from_time)

        if to_time is not None:
            statement = statement.where(MeasurementEvent.created_at <= to_time)

        if offset is not None:
            statement = statement.offset(offset)

        if limit is not None:
            statement = statement.limit(limit)

        return list(self._session.scalars(statement).all())

    def count(
        self,
        *,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> int:
        statement = select(func.count()).select_from(MeasurementEvent)

        if from_time is not None:
            statement = statement.where(MeasurementEvent.created_at >= from_time)

        if to_time is not None:
            statement = statement.where(MeasurementEvent.created_at <= to_time)

        return self._session.execute(statement).scalar_one()

    def get_all_oldest_first(self) -> list[MeasurementEvent]:
        """Every event with its files, in recording order, for exports."""
        statement = (
            select(MeasurementEvent)
            .options(selectinload(MeasurementEvent.files))
            .order_by(
                MeasurementEvent.created_at.asc(),
                MeasurementEvent.id.asc(),
            )
        )
        return list(self._session.scalars(statement).all())

    def delete(self, event_id: int) -> bool:
        event = self._session.get(
            MeasurementEvent,
            event_id,
            options=[selectinload(MeasurementEvent.files)],
        )
        if event is None:
            return False

        file_paths = [saved_file.path for saved_file in event.files]
        self._session.delete(event)
        self._session.commit()

        for relative_path in file_paths:
            self._delete_event_file(relative_path)

        return True

    def prune_oldest_to_fit(self, max_total_bytes: int) -> int:
        """Delete oldest events until the total size of event files fits the cap."""
        if max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be greater than 0")

        events = list(self._session.scalars(self._events_newest_first()).all())

        total_size_bytes = 0
        events_to_remove: list[MeasurementEvent] = []
        for event in events:
            if events_to_remove:
                events_to_remove.append(event)
                continue

            total_size_bytes += self._event_files_size_bytes(event)
            if total_size_bytes > max_total_bytes:
                events_to_remove.append(event)

        if not events_to_remove:
            return 0

        removed_file_paths = [
            saved_file.path
            for event in events_to_remove
            for saved_file in event.files
        ]
        for event in events_to_remove:
            self._session.delete(event)
        self._session.commit()

        for relative_path in removed_file_paths:
            self._delete_event_file(relative_path)

        return len(events_to_remove)

    def _events_newest_first(self) -> Select[tuple[MeasurementEvent]]:
        return (
            select(MeasurementEvent)
            .options(selectinload(MeasurementEvent.files))
            .order_by(
                MeasurementEvent.created_at.desc(),
                MeasurementEvent.id.desc(),
            )
        )

    def _event_files_size_bytes(self, event: MeasurementEvent) -> int:
        total = 0
        for saved_file in event.files:
            try:
                total += resolve_event_file_path(saved_file.path).stat().st_size
            except FileNotFoundError:
                logger.warning(
                    "Event file is missing while computing storage usage: %s",
                    saved_file.path,
                )
            except OSError:
                logger.exception(
                    "Failed to read size of event file %s", saved_file.path
                )
        return total

    def _delete_event_file(self, relative_path: str) -> None:
        try:
            resolve_event_file_path(relative_path).unlink(missing_ok=True)
        except FileNotFoundError:
            logger.warning(
                "Event file is unavailable during cleanup: %s", relative_path
            )
        except OSError:
            logger.exception("Failed to remove event file %s", relative_path)
