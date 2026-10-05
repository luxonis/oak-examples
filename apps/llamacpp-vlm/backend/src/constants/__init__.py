"""Load and validate the app's startup settings."""

import math
from pathlib import Path

import yaml


def validate_max_tokens(value):
    """Return an integer in [1, 256], raising ValueError for invalid input."""
    return integer(value, "Maximum output tokens", 1, 256)


def validate_temperature(value):
    """Return a finite float in [0, 1], raising ValueError for invalid input."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("Temperature must be a number between 0 and 1.")
    return float(value)


def integer(value, name, minimum, maximum=None):
    """Validate inclusive integer bounds, rejecting booleans with ValueError."""
    if (
        type(value) is not int
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        bounds = (
            f"between {minimum} and {maximum}"
            if maximum is not None
            else f"at least {minimum}"
        )
        raise ValueError(f"{name} must be an integer {bounds}.")
    return value


def load_config(path=Path(__file__).with_name("config.yaml")):
    """Load startup configuration and validate settings before app initialization.

    Args:
        path: YAML file path; defaults to config.yaml alongside this module.

    Returns:
        A dictionary containing image, generation, and runtime settings.

    Raises:
        OSError: The configuration file cannot be opened or read.
        yaml.YAMLError: The file is not valid YAML.
        ValueError: Required settings are missing, invalid, or inconsistent.
    """
    with Path(path).open() as stream:
        config = yaml.safe_load(stream)

    # Check the structure before reading individual settings.
    if not isinstance(config, dict):
        raise ValueError(
            "config.yaml must contain image, generation, and runtime sections."
        )
    for section in ("image", "generation", "runtime"):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Missing configuration section: {section}")

    # These settings initialize image preparation and frontend controls.
    integer(config["image"].get("max_edge"), "image.max_edge", 224, 896)
    validate_max_tokens(config["generation"].get("max_tokens"))
    validate_temperature(config["generation"].get("temperature"))

    # Reject invalid server settings before starting the camera or model.
    runtime = config["runtime"]
    for key in (
        "context_size",
        "threads",
        "batch_size",
        "ubatch_size",
        "image_min_tokens",
        "image_max_tokens",
    ):
        integer(runtime.get(key), f"runtime.{key}", 1)
    integer(runtime.get("cache_ram_mb"), "runtime.cache_ram_mb", 0)

    if runtime["ubatch_size"] > runtime["batch_size"]:
        raise ValueError("runtime.ubatch_size must not exceed batch_size.")
    if runtime["image_min_tokens"] > runtime["image_max_tokens"]:
        raise ValueError("runtime.image_min_tokens must not exceed image_max_tokens.")

    if runtime.get("flash_attention") not in ("auto", "on", "off"):
        raise ValueError(
            'runtime.flash_attention must be "auto", "on", or "off" (quote on/off in YAML).'
        )

    for key in ("fit", "context_shift"):
        if type(runtime.get(key)) is not bool:
            raise ValueError(f"runtime.{key} must be true or false.")

    return config
