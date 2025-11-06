from typing import TypedDict


class ThresholdUpdatePayload(TypedDict):
    """Payload for updating NN confidence threshold."""

    threshold: float
