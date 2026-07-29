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
from .metadata import (
    LEGACY_TO_CANONICAL,
    MetadataValidationError,
    normalize_eml_metadata,
    validate_metadata,
)

__all__ = [
    "ConfigError",
    "collection_names",
    "load_collection",
    "load_default",
    "load_eml_config",
    "merge_config",
    "render_eml",
    "LEGACY_TO_CANONICAL",
    "MetadataValidationError",
    "normalize_eml_metadata",
    "validate_metadata",
]

__version__ = "0.4.1"
