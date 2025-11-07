from dataclasses import dataclass, field


@dataclass
class ModelState:
    """Holds current NN model prompt state"""

    confidence_threshold: float = 0.1
    current_classes: list[str] = field(default_factory=list)
