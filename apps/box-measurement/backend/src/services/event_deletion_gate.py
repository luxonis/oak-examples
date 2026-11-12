import threading


class EventDeletionGate:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._export_in_progress = False
        self._active_deletions = 0

    def begin_export(self) -> None:
        with self._condition:
            if self._export_in_progress:
                raise RuntimeError("An export is already in progress")

            self._export_in_progress = True
            try:
                while self._active_deletions > 0:
                    self._condition.wait()
            except BaseException:
                self._export_in_progress = False
                self._condition.notify_all()
                raise

    def end_export(self) -> None:
        with self._condition:
            self._export_in_progress = False
            self._condition.notify_all()

    def try_begin_deletion(self) -> bool:
        with self._condition:
            if self._export_in_progress:
                return False
            self._active_deletions += 1
            return True

    def end_deletion(self) -> None:
        with self._condition:
            if self._active_deletions <= 0:
                raise RuntimeError("No event deletion is active")
            self._active_deletions -= 1
            self._condition.notify_all()
