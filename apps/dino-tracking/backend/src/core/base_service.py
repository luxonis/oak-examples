from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class BaseService(ABC, Generic[PayloadT]):
    """
    Base class for all backend services with payload validation.
    """

    NAME: str
    PAYLOAD_MODEL: type[PayloadT] | None = None

    @abstractmethod
    def handle(self, payload: PayloadT | None = None) -> dict:
        pass
