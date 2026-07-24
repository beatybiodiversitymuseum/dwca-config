"""Installable access to Beaty Biodiversity Museum DwCA configuration."""

from .config import (
    ConfigError,
    collection_names,
    load_collection,
    load_default,
    load_eml_config,
    merge_config,
    render_eml,
)

__all__ = [
    "ConfigError",
    "collection_names",
    "load_collection",
    "load_default",
    "load_eml_config",
    "merge_config",
    "render_eml",
]

__version__ = "0.2.0"
