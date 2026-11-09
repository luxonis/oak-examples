"""Register typed JSON services with the DepthAI remote connection."""

import inspect
import logging
from typing import Any, Callable

import depthai as dai
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class EmptyBody(BaseModel):
    pass


class ErrorResponse(BaseModel):
    error: str


def _format_validation_error(error: ValidationError) -> str:
    formatted_errors = [
        f"{validation_error['loc'][-1]} - {validation_error['msg']}\n"
        for validation_error in error.errors()
    ]
    return ", ".join(formatted_errors)


def _get_model_type(annotation: Any, label: str) -> type[BaseModel]:
    if annotation is inspect._empty:
        raise TypeError(f"{label} must be type-annotated")

    if not isinstance(annotation, type) or not issubclass(annotation, BaseModel):
        raise TypeError(
            f"{label} must be a subclass of pydantic.BaseModel, got {annotation}"
        )

    return annotation


def add_request_handler(
    visualizer: dai.RemoteConnection,
    service_name: str,
    handler: Callable,
):
    """Register a JSON service whose request and response are Pydantic models.

    The handler's single parameter and return type must be annotated with
    ``BaseModel`` subclasses. Validation and handler failures become JSON
    error responses instead of escaping the service callback.

    Args:
        visualizer: Connection that exposes the service.
        service_name: Name clients use to call it.
        handler: Typed request-to-response callback.
    """
    # Infer the payload type from the handler's annotation.
    sig = inspect.signature(handler)
    params = list(sig.parameters.values())
    if len(params) != 1:
        raise TypeError(f"Handler {handler.__name__} must take exactly one parameter")

    payload_type = _get_model_type(
        params[0].annotation,
        f"First parameter of {handler.__name__}",
    )
    response_type = _get_model_type(
        sig.return_annotation,
        f"Return type of {handler.__name__}",
    )

    def _handler(request: Any) -> dict:
        logger.debug(f"Handling request for service {service_name}, request: {request}")
        try:
            validated_request = payload_type.model_validate(request)
            response = handler(validated_request)
            validated_response = response_type.model_validate(response)
            response_json = validated_response.model_dump(mode="json")
            logger.debug(
                f"Returning response for service {service_name}: {response_json}"
            )
            return response_json
        except ValidationError as e:
            logger.exception(f"Error validating request for service {service_name}")
            return ErrorResponse(error=_format_validation_error(e)).model_dump(
                mode="json"
            )
        except Exception as e:
            logger.exception(f"Error handling request for service {service_name}")
            response = ErrorResponse(error=str(e))
            return response.model_dump(mode="json")

    visualizer.registerService(service_name, _handler)
    logger.info(f"Registered service {service_name}")
