"""Load the YAML configuration shipped with :mod:`dwca_config`."""

from copy import deepcopy
from importlib.resources import files
from typing import Any, Dict, Mapping

import yaml

from .eml import merge_eml, render_eml_document
from .metadata import legacy_eml_metadata, normalize_eml_metadata


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
    """Load a fresh copy of the canonical EML metadata contract."""

    resolved = load_collection(name).get("dwca_metadata")
    if not isinstance(resolved, dict):
        raise ConfigError(f"Resolved EML configuration for {name!r} is invalid")
    return deepcopy(resolved)


def render_eml(name: str, **publishing_state: Any) -> str:
    """Render a collection's resolved configuration as standalone EML XML."""

    canonical = load_eml_config(name)
    publication = canonical["publication_date"]
    if "publication_date" not in publishing_state and not publication.get("automatic"):
        publishing_state["publication_date"] = publication["value"]
    return render_eml_document(
        legacy_eml_metadata(canonical), **publishing_state
    )


def _eml_text(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    return value.get("#content", value.get("#text"))


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
        defaults = resolved.setdefault("dwca_defaults", {})
        if not defaults.get("datasetName"):
            defaults["datasetName"] = resolved["eml_metadata"].get("datasetTitle")
        resolved["dwca_metadata"] = normalize_eml_metadata(
            resolved["eml_metadata"],
            dataset_id=defaults.get("datasetID"),
        )
    return resolved
