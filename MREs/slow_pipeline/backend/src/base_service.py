from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

PayloadT = TypeVar("PayloadT", bound=BaseModel | None)


class BaseService(ABC, Generic[PayloadT]):
    """
    Service boundary:
      - called with JSON-ish payload (typically dict)
      - validates using PAYLOAD_MODEL
      - calls handle_typed() with a Pydantic model (or None)
    """

    NAME: ClassVar[str]
    PAYLOAD_MODEL: ClassVar[type[PayloadT]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "BaseService":
            return

        if (
            not hasattr(cls, "NAME")
            or not isinstance(cls.NAME, str)
            or not cls.NAME.strip()
        ):
            raise TypeError(f"{cls.__name__} must define NAME as a non-empty string.")

        if not hasattr(cls, "PAYLOAD_MODEL"):
            raise TypeError(
                f"{cls.__name__} must define PAYLOAD_MODEL (type[BaseModel] | None)."
            )

        model = cls.PAYLOAD_MODEL
        if model is not None:
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                raise TypeError(
                    f"{cls.__name__}.PAYLOAD_MODEL must be a Pydantic BaseModel subclass or None."
                )

    def __call__(self, payload: Any) -> dict:
        """
        Handle incoming request with automatic validation.

        On success: returns handle_typed() return dict.
        On failure: returns {"ok": False, "error": ...}
        """
        try:
            validated = self._validate(payload)
            return self.handle_typed(validated)
        except ValidationError as e:
            self.on_validation_error(e)
            return {"ok": False, "error": e.errors()}
        except Exception as e:
            self.on_internal_error(e)
            return {"ok": False, "error": str(e)}

    def _validate(self, payload: Any) -> PayloadT | None:
        if self.PAYLOAD_MODEL is None:
            return None
        return self.PAYLOAD_MODEL.model_validate(payload)

    def on_validation_error(self, e: ValidationError) -> None:
        """Called when payload validation fails. Override for custom logging."""
        pass

    def on_internal_error(self, e: Exception) -> None:
        """Called when service raises an exception. Override for custom logging."""
        pass

    @abstractmethod
    def handle_typed(self, payload: PayloadT | None) -> dict:
        """
        Implement service logic with validated payload.
        """
        raise NotImplementedError
