from datetime import datetime, timezone
import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MeasurementEventType(str, enum.Enum):
    SUCCESS = "SUCCESS"
    INCOMPLETE = "INCOMPLETE"
    FAILED_LOW_COVERAGE = "FAILED_LOW_COVERAGE"


class MeasurementEvent(Base):
    __tablename__ = "measurement_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    event_type: Mapped[MeasurementEventType] = mapped_column(
        Enum(MeasurementEventType, native_enum=False), nullable=False
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    length_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_mm3: Mapped[float | None] = mapped_column(Float, nullable=True)
    files: Mapped[list["MeasurementEventFile"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )


class MeasurementEventFile(Base):
    __tablename__ = "measurement_event_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_events.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    event: Mapped[MeasurementEvent] = relationship(back_populates="files")
