"""Public calibration settings, controls, and terminal results."""

from enum import Enum
from typing import ClassVar, TypeAlias

import depthai as dai
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from solutions_sdk.box_measurement.message.support_plane import SupportPlane


class PlaneCalibrationConfig(BaseModel):
    """Plane-fitting settings for ``SupportPlaneCalibrator``, fixed at build."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    distance_threshold_mm: FiniteFloat = Field(default=10.0, gt=0)
    ransac_sample_points: int = Field(default=3, ge=3)
    ransac_max_iterations: int = Field(default=300, ge=1)
    max_plane_passes: int = Field(default=10, ge=1)
    min_inlier_ratio: FiniteFloat = Field(default=0.05, ge=0, le=1)
    voxel_size_mm: FiniteFloat = Field(default=30.0, gt=0)
    max_gravity_angle_deg: FiniteFloat = Field(default=6.5, ge=0, lt=90)
    merge_distance_threshold_mm: FiniteFloat = Field(default=25.0, gt=0)


class CalibrationOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class _Command(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class SupportPlaneCalibrationControl(dai.Buffer):
    """Create controls using start(), stop(), reset(), and verify(plane).

    Like DepthAI's DynamicCalibrationControl, each control carries one command.
    """

    class Commands:
        class Start(_Command):
            """Begin an attempt unless one is running or awaits reset."""

        class Stop(_Command):
            """Cancel the running attempt and return to idle without reset."""

        class Reset(_Command):
            """Allow a new attempt after the previous one succeeded or failed."""

        class Verify(_Command):
            """Check a plane against gravity without affecting any attempt."""

            plane: SupportPlane

    # At the move to solutions-sdk (Python 3.12+), make this a `type` alias
    # (ruff UP040); isinstance then needs `Command.__value__`.
    Command: TypeAlias = (
        Commands.Start | Commands.Stop | Commands.Reset | Commands.Verify
    )

    def __init__(self, command: Command) -> None:
        super().__init__()
        if not isinstance(command, self.Command):
            raise TypeError("Unknown calibration control")
        self._command = command

    @property
    def command(self) -> Command:
        return self._command

    @classmethod
    def start(cls) -> "SupportPlaneCalibrationControl":
        return cls(cls.Commands.Start())

    @classmethod
    def stop(cls) -> "SupportPlaneCalibrationControl":
        return cls(cls.Commands.Stop())

    @classmethod
    def reset(cls) -> "SupportPlaneCalibrationControl":
        return cls(cls.Commands.Reset())

    @classmethod
    def verify(cls, plane: SupportPlane) -> "SupportPlaneCalibrationControl":
        return cls(cls.Commands.Verify(plane=plane))


class SupportPlaneCalibrationResult(dai.Buffer):
    def __init__(
        self,
        outcome: CalibrationOutcome,
        candidates: list[SupportPlane],
        info: str = "",
    ) -> None:
        super().__init__()
        if not isinstance(outcome, CalibrationOutcome):
            raise TypeError("Unknown calibration outcome")
        if bool(candidates) != (outcome is CalibrationOutcome.SUCCEEDED):
            raise ValueError("Only successful calibration has candidates")
        if any(not isinstance(plane, SupportPlane) for plane in candidates):
            raise TypeError("Candidates must be support planes")
        self._outcome = outcome
        self._candidates = tuple(candidates)
        self._info = info

    @property
    def outcome(self) -> CalibrationOutcome:
        return self._outcome

    @property
    def candidates(self) -> tuple[SupportPlane, ...]:
        """Accepted planes, best first; empty unless calibration succeeded."""
        return self._candidates

    @property
    def info(self) -> str:
        return self._info


class SupportPlaneVerificationResult(dai.Buffer):
    """Whether a supplied plane passes calibration's gravity check."""

    def __init__(
        self, plane: SupportPlane, gravity_angle_deg: float, accepted: bool
    ) -> None:
        super().__init__()
        if not isinstance(plane, SupportPlane):
            raise TypeError("Verification expects a support plane")
        self._plane = plane
        self._gravity_angle_deg = float(gravity_angle_deg)
        self._accepted = bool(accepted)

    @property
    def plane(self) -> SupportPlane:
        return self._plane

    @property
    def gravity_angle_deg(self) -> float:
        return self._gravity_angle_deg

    @property
    def accepted(self) -> bool:
        return self._accepted
