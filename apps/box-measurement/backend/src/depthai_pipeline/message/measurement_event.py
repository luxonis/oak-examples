import enum

import depthai as dai


class MeasurementEventKind(str, enum.Enum):
    SUCCESS = "SUCCESS"
    INCOMPLETE = "INCOMPLETE"
    FAILED_LOW_COVERAGE = "FAILED_LOW_COVERAGE"


class MeasurementUpdate(dai.Buffer):
    """Carries the last received aggregate for a completed successful track;
    the application saver patches the stored event with it."""

    def __init__(
        self,
        track_id: int,
        length_mm: float,
        width_mm: float,
        height_mm: float,
        volume_mm3: float,
    ):
        super().__init__()
        self.track_id = track_id
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.volume_mm3 = volume_mm3


class MeasurementEventTrigger(dai.Buffer):
    def __init__(
        self,
        kind: MeasurementEventKind,
        track_id: int,
        length_mm: float | None = None,
        width_mm: float | None = None,
        height_mm: float | None = None,
        volume_mm3: float | None = None,
    ):
        super().__init__()
        self.kind = kind
        self.track_id = track_id
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.volume_mm3 = volume_mm3
