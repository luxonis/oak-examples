from typing import TypedDict, List


class ClassUpdatePayload(TypedDict):
    """Payload for updating detection classes."""

    classes: List[str]
