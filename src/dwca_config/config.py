"""Load the YAML configuration shipped with :mod:`dwca_config`."""

from copy import deepcopy
from importlib.resources import files
from typing import Any, Dict, Mapping

import yaml


class ConfigError(ValueError):
    """Raised when packaged configuration is missing or malformed."""


def _data_root():
    return files("dwca_config").joinpath("data")


def _load_yaml(resource) -> Dict[str, Any]:
    try:
        parsed = yaml.safe_load(resource.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not load configuration from {resource.name}") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"Configuration in {resource.name} must be a mapping")
    return parsed


def collection_names() -> tuple[str, ...]:
    """Return the available collection names in deterministic order."""

    directory = _data_root().joinpath("collections")
    return tuple(
        sorted(
            item.name.removesuffix(".yaml")
            for item in directory.iterdir()
            if item.is_file() and item.name.endswith(".yaml")
        )
    )


def load_default() -> Dict[str, Any]:
    """Load a fresh copy of the institution-wide default configuration."""

    return _load_yaml(_data_root().joinpath("default.yaml"))


def merge_config(
    base: Mapping[str, Any], override: Mapping[str, Any]
) -> Dict[str, Any]:
    """Recursively merge ``override`` over ``base`` without mutating either."""

    result: Dict[str, Any] = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_collection(name: str, *, merged: bool = True) -> Dict[str, Any]:
    """Load one collection, recursively merged over defaults by default."""

    available = collection_names()
    if name not in available:
        choices = ", ".join(available)
        raise ConfigError(f"Unknown collection {name!r}; choose one of: {choices}")
    collection = _load_yaml(
        _data_root().joinpath("collections", f"{name}.yaml")
    )
    return merge_config(load_default(), collection) if merged else collection
