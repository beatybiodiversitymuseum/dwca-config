"""Load the YAML configuration shipped with :mod:`dwca_config`."""

from copy import deepcopy
from importlib.resources import files
from typing import Any, Dict, Mapping

import yaml

from .eml import merge_eml, render_eml_document


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


def load_eml_config(name: str) -> Dict[str, Any]:
    """Load resolved EML from the main collection configuration."""

    resolved = load_collection(name).get("eml_metadata")
    if not isinstance(resolved, dict):
        raise ConfigError(f"Resolved EML configuration for {name!r} is invalid")
    return deepcopy(resolved)


def render_eml(name: str, **publishing_state: Any) -> str:
    """Render a collection's resolved configuration as standalone EML XML."""

    return render_eml_document(load_eml_config(name), **publishing_state)


def _eml_text(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    return value.get("#content", value.get("#text"))


def _metadata_projection(eml: Mapping[str, Any]) -> Dict[str, Any]:
    creators = eml.get("creators", [])
    creator = creators[0] if isinstance(creators, list) and creators else {}
    return {
        "title": eml.get("datasetTitle"),
        "description": eml.get("abstract"),
        "organization": (
            creator.get("organizationName")
            if isinstance(creator, Mapping)
            else None
        ),
    }


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
    if not merged:
        return collection

    default = load_default()
    shared_eml = default.pop("eml_metadata", {})
    collection_eml = collection.pop("eml_metadata", {})
    resolved = merge_config(default, collection)
    if shared_eml or collection_eml:
        resolved["eml_metadata"] = merge_eml(shared_eml, collection_eml)
        projected = _metadata_projection(resolved["eml_metadata"])
        metadata = merge_config(resolved.get("dwca_metadata", {}), projected)
        defaults = resolved.setdefault("dwca_defaults", {})
        metadata["dataset_id"] = defaults.get("datasetID")
        if not defaults.get("datasetName"):
            defaults["datasetName"] = projected.get("title")
        resolved["dwca_metadata"] = metadata
    return resolved
