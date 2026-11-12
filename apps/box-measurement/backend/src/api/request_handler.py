import inspect
import json
import logging
from typing import Any, Callable, get_args

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


def _validate_binary_return_type(annotation: Any, label: str) -> None:
    if annotation is bytes:
        return

    if set(get_args(annotation)) == {bytes, type(None)}:
        return

    raise TypeError(f"{label} must be annotated as bytes | None, got {annotation}")


def add_request_handler(
    visualizer: dai.RemoteConnection,
    service_name: str,
    handler: Callable,
):
    # infer payload type from handler annotation
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


def add_binary_request_handler(
    visualizer: dai.RemoteConnection,
    service_name: str,
    handler: Callable,
):
    sig = inspect.signature(handler)
    params = list(sig.parameters.values())
    if len(params) != 1:
        raise TypeError(f"Handler {handler.__name__} must take exactly one parameter")

    payload_type = _get_model_type(
        params[0].annotation,
        f"First parameter of {handler.__name__}",
    )
    _validate_binary_return_type(
        sig.return_annotation,
        f"Return type of {handler.__name__}",
    )

    def _handler(request: bytes) -> bytes | None:
        logger.debug(f"Handling binary request for service {service_name}")
        try:
            request_json = json.loads(request.decode("utf-8"))
            validated_request = payload_type.model_validate(request_json)
            response = handler(validated_request)
            if response is not None and not isinstance(response, bytes):
                raise TypeError(
                    f"Binary handler {handler.__name__} must return bytes | None"
                )
            return response
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.exception(
                f"Error decoding binary request payload for service {service_name}"
            )
            return None
        except ValidationError:
            logger.exception(f"Error validating request for service {service_name}")
            return None
        except Exception:
            logger.exception(f"Error handling request for service {service_name}")
            return None

    visualizer.registerBinaryService(service_name, _handler)
    logger.info(f"Registered binary service {service_name}")
