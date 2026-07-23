"""Installable access to Beaty Biodiversity Museum DwCA configuration."""

from .config import ConfigError, collection_names, load_collection, load_default, merge_config

__all__ = [
    "ConfigError",
    "collection_names",
    "load_collection",
    "load_default",
    "merge_config",
]

__version__ = "0.1.0"
