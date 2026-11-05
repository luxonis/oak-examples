import depthai as dai

from .danger_classification import DangerLevel, DangerSource, DangerSpatialDetection


class DangerAssessment(dai.Buffer):
    """One detector's raw alert, availability, and nearest ground-frame point.

    ``available`` distinguishes an actual SAFE result from missing spatial
    context, such as an unavailable ground orientation.
    """

    def __init__(self):
        super().__init__()
        self._source: DangerSource = DangerSource.SEGMENTATION
        self._level: DangerLevel = DangerLevel.SAFE
        self._available = True
        self._danger_detections: list[DangerSpatialDetection] = []
        self._nearest_point_mm: tuple[float, float, float] | None = None

    @property
    def source(self) -> DangerSource:
        return self._source

    @source.setter
    def source(self, value: DangerSource):
        if not isinstance(value, DangerSource):
            raise TypeError(
                f"source must be a DangerSource, got {type(value).__name__}"
            )
        self._source = value

    @property
    def level(self) -> DangerLevel:
        return self._level

    @level.setter
    def level(self, value: DangerLevel):
        if not isinstance(value, DangerLevel):
            raise TypeError(f"level must be a DangerLevel, got {type(value).__name__}")
        self._level = value

    @property
    def available(self) -> bool:
        return self._available

    @available.setter
    def available(self, value: bool):
        self._available = bool(value)

    @property
    def danger_detections(self) -> list[DangerSpatialDetection]:
        return self._danger_detections

    @danger_detections.setter
    def danger_detections(self, value: list[DangerSpatialDetection]):
        self._danger_detections = list(value)

    @property
    def nearest_point_mm(self) -> tuple[float, float, float] | None:
        return self._nearest_point_mm

    @nearest_point_mm.setter
    def nearest_point_mm(self, value: tuple[float, float, float] | None):
        self._nearest_point_mm = value
