from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel

from core.neural_network.prompts.nn_prompts_controller import NnPromptsController
from core.neural_network.prompts.handlers.base_prompt_handler import BasePromptHandler
from core.service_name import ServiceName

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class BaseService(ABC, Generic[PayloadT]):
    NAME: ServiceName

    def __init__(
        self,
        controller: NnPromptsController | None = None,
        handler: BasePromptHandler | None = None,
    ):
        self._controller = controller
        self._handler = handler
        self.__name = self.NAME

    @abstractmethod
    def handle(self, payload: PayloadT) -> dict[str, any]:
        """Execute service logic and return a JSON-serializable response."""
        pass

    @property
    def name(self) -> ServiceName:
        return self.__name
