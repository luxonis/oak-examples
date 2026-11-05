"""Bounded event history whose files live only in this app process's temp directory."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock


class DangerEventType(str, Enum):
    WARNING = "WARNING"
    DANGER = "DANGER"


@dataclass
class DangerTriggerEventFileData:
    """A file attached to an event, named relative to the event directory."""

    name: str
    path: str


@dataclass
class DangerTriggerEventData:
    """One alert and its captured files; IDs are assigned on insertion."""

    frame_timestamp_seconds: float
    triggered_at: datetime
    event_type: DangerEventType
    files: list[DangerTriggerEventFileData] = field(default_factory=list)
    id: int = 0


class EventStore:
    """Keep newest events in memory and their files in a temporary directory.

    Args:
        limit: Maximum number of retained events.
        max_bytes: Disk budget for retained files; the newest event is kept
            even when it alone exceeds this budget.
    """

    def __init__(self, limit: int, max_bytes: int = 1_000_000_000):
        self._directory = TemporaryDirectory(prefix="safeguard-events-")
        self.files_dir = Path(self._directory.name)
        self._events: deque[DangerTriggerEventData] = deque()
        self._limit = limit
        self._max_bytes = max_bytes
        self._next_id = 1
        self._lock = Lock()

    def add(self, event: DangerTriggerEventData) -> None:
        with self._lock:
            event.id = self._next_id
            self._next_id += 1
            self._events.appendleft(event)
            self._prune()

    def set_limit(self, limit: int) -> None:
        with self._lock:
            self._limit = limit
            self._prune()

    def list(
        self, offset: int = 0, limit: int | None = None
    ) -> tuple[list[DangerTriggerEventData], int]:
        """Return a newest-first page and the total count before pagination."""
        with self._lock:
            events = list(self._events)
        return (
            events[offset : offset + limit if limit is not None else None],
            len(events),
        )

    def read_file(self, name: str) -> bytes | None:
        """Read a retained event file, or return None if unavailable or unlisted."""
        # Only serve files still associated with a retained event.
        if Path(name).name != name:
            return None
        with self._lock:
            allowed = any(
                file.path == name for event in self._events for file in event.files
            )
            if not allowed:
                return None
            try:
                return (self.files_dir / name).read_bytes()
            except OSError:
                return None

    def delete_file(self, name: str) -> None:
        (self.files_dir / Path(name).name).unlink(missing_ok=True)

    def _prune(self) -> None:
        # The UI count is an upper bound; also keep temporary clips within a
        # predictable disk budget. Preserve the newest event even if it alone
        # exceeds the budget so its capture can still be inspected.
        while len(self._events) > self._limit or (
            len(self._events) > 1 and self._total_bytes() > self._max_bytes
        ):
            old = self._events.pop()
            for file in old.files:
                self.delete_file(file.path)

    def _total_bytes(self) -> int:
        total = 0
        for event in self._events:
            for file in event.files:
                try:
                    total += (self.files_dir / Path(file.path).name).stat().st_size
                except OSError:
                    pass
        return total

    def close(self) -> None:
        """Remove the temporary event directory and all remaining files."""
        self._directory.cleanup()
