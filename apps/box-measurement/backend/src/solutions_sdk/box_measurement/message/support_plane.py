"""Portable support-plane geometry, independent of running pipeline nodes."""

import json
import math
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator


class SupportPlane(BaseModel):
    """The normalized equation ``normal · point + offset_mm = 0`` in millimeters."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    normal: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    offset_mm: FiniteFloat

    @model_validator(mode="after")
    def _normalize(self) -> "SupportPlane":
        # Scaling first keeps normalization safe for very large finite normals.
        scale = max(abs(value) for value in self.normal)
        if scale == 0:
            raise ValueError("Support-plane normal must be nonzero")
        scaled = tuple(value / scale for value in self.normal)
        length = math.hypot(*scaled)
        normalized_offset = (self.offset_mm / scale) / length
        if not math.isfinite(normalized_offset):
            raise ValueError("Normalized support-plane offset must be finite")
        # The model is frozen; normalization is part of construction.
        object.__setattr__(self, "normal", tuple(value / length for value in scaled))
        object.__setattr__(self, "offset_mm", normalized_offset)
        return self

    def toJson(self) -> dict:
        """Return normalized geometry without application or coordinate metadata."""
        return {"normal": list(self.normal), "offset_mm": self.offset_mm}

    @classmethod
    def fromJson(cls, data: dict) -> "SupportPlane":
        if not isinstance(data, dict):
            raise TypeError("Expected a support-plane JSON object")
        if set(data) != {"normal", "offset_mm"}:
            raise ValueError("Expected support-plane normal and offset_mm")
        normal = data["normal"]
        offset = data["offset_mm"]
        if not isinstance(normal, (list, tuple)):
            raise TypeError("Support-plane normal must be a list")
        if len(normal) != 3:
            raise ValueError("Support-plane normal must have three components")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in (*normal, offset)
        ):
            raise TypeError("Support-plane geometry must contain numeric values")
        return cls(normal=tuple(normal), offset_mm=offset)

    def toJsonFile(self, path: str | Path) -> None:
        """Write explicitly to a caller-selected path; file errors propagate."""
        Path(path).write_text(
            json.dumps(self.toJson(), allow_nan=False), encoding="utf-8"
        )

    @classmethod
    def fromJsonFile(cls, path: str | Path) -> "SupportPlane":
        return cls.fromJson(json.loads(Path(path).read_text(encoding="utf-8")))
