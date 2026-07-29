"""Canonical EML metadata normalization and validation."""

from copy import deepcopy
from datetime import date
import re
from typing import Any, Dict, Mapping
from urllib.parse import urlparse


class MetadataValidationError(ValueError):
    """Raised when canonical EML metadata is malformed."""


LEGACY_TO_CANONICAL = {
    "languageCode": "language",
    "datasetTitle": "title",
    "alternateIdentifiers": "alternate_identifiers",
    "creators": "creators",
    "metadataProviders": "metadata_providers",
    "associatedParties": "associated_parties",
    "abstract": "description",
    "publicationDate": "publication_date",
    "keywordSets": "keyword_sets",
    "intellectualRights": "intellectual_rights",
    "license": "license",
    "distributions": "distributions",
    "geographicCoverage": "geographic_coverage",
    "taxonomicCoverage": "taxonomic_coverage",
    "temporalCoverage": "temporal_coverage",
    "maintenance": "maintenance",
    "contacts": "contacts",
    "methods": "methods",
    "project": "project",
    "additionalInfo": "additional_info",
    "bibliography": "bibliography",
    "externalDataSets": "external_datasets",
    "resourceLogoUrl": "resource_logo_url",
    "collection": "collection",
    "formationPeriod": "formation_period",
    "preservationMethods": "preservation_methods",
    "curatorialUnits": "curatorial_units",
    "gbifMetadata": "gbif_metadata",
}


def _snake(name: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _snake_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {_snake(str(key)): _snake_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snake_value(item) for item in value]
    return deepcopy(value)


def normalize_eml_metadata(
    legacy: Mapping[str, Any], *, dataset_id: Any = None
) -> Dict[str, Any]:
    """Convert the complete IPT-era mapping to the canonical public contract."""

    canonical = {
        LEGACY_TO_CANONICAL.get(key, _snake(key)): _snake_value(value)
        for key, value in legacy.items()
    }
    alternates = canonical.get("alternate_identifiers", [])
    if not isinstance(alternates, list):
        alternates = [alternates]
    if dataset_id is None and alternates:
        dataset_id = alternates[0]
    canonical["dataset_id"] = deepcopy(dataset_id)
    canonical["alternate_identifiers"] = deepcopy(alternates)
    canonical.setdefault("publication_date", {"automatic": True})
    validate_metadata(canonical)
    return canonical


def legacy_eml_metadata(canonical: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the deprecated camelCase renderer vocabulary."""

    reverse = {value: key for key, value in LEGACY_TO_CANONICAL.items()}

    def camel_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                "".join(
                    part if index == 0 else part.title()
                    for index, part in enumerate(str(key).split("_"))
                ): camel_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [camel_value(item) for item in value]
        return deepcopy(value)

    legacy = {
        reverse.get(key, key): camel_value(value)
        for key, value in canonical.items()
        if key != "dataset_id"
    }
    legacy["datasetID"] = deepcopy(canonical.get("dataset_id"))
    return legacy


def _fail(path: str, message: str) -> None:
    raise MetadataValidationError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    return value


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        _fail(path, "must be a list")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        _fail(path, "must be a non-empty string")


def _url(value: Any, path: str) -> None:
    _string(value, path)
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        _fail(path, "must be an absolute HTTP(S) URL")


def _required(obj: Mapping[str, Any], path: str, *keys: str) -> None:
    for key in keys:
        if key not in obj:
            _fail(f"{path}.{key}", "is required")


def _party(value: Any, path: str) -> None:
    party = _mapping(value, path)
    if not any(
        isinstance(party.get(key), str) and party[key].strip()
        for key in ("given_name", "sur_name", "organization_name")
    ):
        _fail(path, "requires a person name or organization_name")
    for key in (
        "given_name", "sur_name", "organization_name", "position_name",
        "phone", "email", "role",
    ):
        if key in party:
            _string(party[key], f"{path}.{key}")
    if "online_url" in party:
        _url(party["online_url"], f"{path}.online_url")
    if "address" in party:
        address = _mapping(party["address"], f"{path}.address")
        for key, item in address.items():
            _string(item, f"{path}.address.{key}")
    if "user_id" in party:
        user_id = _mapping(party["user_id"], f"{path}.user_id")
        _required(user_id, f"{path}.user_id", "value", "directory")
        _string(user_id["value"], f"{path}.user_id.value")
        _url(user_id["directory"], f"{path}.user_id.directory")


def _records(metadata: Mapping[str, Any], key: str, validator) -> None:
    for index, item in enumerate(_list(metadata.get(key, []), key)):
        validator(item, f"{key}[{index}]")


def validate_metadata(metadata: Mapping[str, Any]) -> None:
    """Validate the complete canonical GBIF-profile EML metadata contract."""

    metadata = _mapping(metadata, "dwca_metadata")
    _required(
        metadata, "dwca_metadata", "dataset_id", "alternate_identifiers",
        "title", "description", "language", "creators", "metadata_providers",
        "contacts", "publication_date", "intellectual_rights",
    )
    _string(metadata["dataset_id"], "dataset_id")
    _string(metadata["title"], "title")
    _string(metadata["description"], "description")
    _string(metadata["language"], "language")
    for index, item in enumerate(_list(metadata["alternate_identifiers"], "alternate_identifiers")):
        _string(item, f"alternate_identifiers[{index}]")
    for key in ("creators", "metadata_providers", "associated_parties", "contacts"):
        _records(metadata, key, _party)
    if not metadata["creators"] or not metadata["contacts"]:
        _fail("dwca_metadata", "creators and contacts must not be empty")

    publication = _mapping(metadata["publication_date"], "publication_date")
    if publication.get("automatic") is True:
        if "value" in publication:
            _fail("publication_date", "automatic and value are mutually exclusive")
    else:
        _required(publication, "publication_date", "value")
        try:
            date.fromisoformat(publication["value"])
        except (TypeError, ValueError):
            _fail("publication_date.value", "must be an ISO 8601 date")

    rights = _mapping(metadata["intellectual_rights"], "intellectual_rights")
    _required(rights, "intellectual_rights", "text")
    _string(rights["text"], "intellectual_rights.text")
    if "link" in rights:
        link = _mapping(rights["link"], "intellectual_rights.link")
        _required(link, "intellectual_rights.link", "url", "title")
        _url(link["url"], "intellectual_rights.link.url")
        _string(link["title"], "intellectual_rights.link.title")

    if "license" in metadata:
        license_value = _mapping(metadata["license"], "license")
        _required(license_value, "license", "name", "url", "identifier")
        _string(license_value["name"], "license.name")
        _url(license_value["url"], "license.url")
        _string(license_value["identifier"], "license.identifier")

    for index, item in enumerate(_list(metadata.get("keyword_sets", []), "keyword_sets")):
        item = _mapping(item, f"keyword_sets[{index}]")
        _required(item, f"keyword_sets[{index}]", "keywords", "thesaurus")
        for offset, keyword in enumerate(_list(item["keywords"], f"keyword_sets[{index}].keywords")):
            _string(keyword, f"keyword_sets[{index}].keywords[{offset}]")
        _string(item["thesaurus"], f"keyword_sets[{index}].thesaurus", allow_empty=True)

    for index, item in enumerate(_list(metadata.get("distributions", []), "distributions")):
        item = _mapping(item, f"distributions[{index}]")
        _required(item, f"distributions[{index}]", "scope", "function", "url")
        _string(item["scope"], f"distributions[{index}].scope")
        _string(item["function"], f"distributions[{index}].function")
        _url(item["url"], f"distributions[{index}].url")

    if "geographic_coverage" in metadata:
        coverage = _mapping(metadata["geographic_coverage"], "geographic_coverage")
        _required(coverage, "geographic_coverage", "description", "west", "east", "north", "south")
        _string(coverage["description"], "geographic_coverage.description", allow_empty=True)
        bounds = {"west": (-180, 180), "east": (-180, 180), "north": (-90, 90), "south": (-90, 90)}
        for key, (minimum, maximum) in bounds.items():
            try:
                coordinate = float(coverage[key])
            except (TypeError, ValueError):
                _fail(f"geographic_coverage.{key}", "must be numeric")
            if not minimum <= coordinate <= maximum:
                _fail(f"geographic_coverage.{key}", f"must be between {minimum} and {maximum}")
        if float(coverage["west"]) > float(coverage["east"]):
            _fail("geographic_coverage", "west must not exceed east")
        if float(coverage["south"]) > float(coverage["north"]):
            _fail("geographic_coverage", "south must not exceed north")

    if "taxonomic_coverage" in metadata:
        coverage = _mapping(metadata["taxonomic_coverage"], "taxonomic_coverage")
        _required(coverage, "taxonomic_coverage", "description", "classifications")
        _string(coverage["description"], "taxonomic_coverage.description", allow_empty=True)
        for index, item in enumerate(_list(coverage["classifications"], "taxonomic_coverage.classifications")):
            item = _mapping(item, f"taxonomic_coverage.classifications[{index}]")
            _required(item, f"taxonomic_coverage.classifications[{index}]", "rank_name", "rank_value")
            _string(item["rank_name"], f"taxonomic_coverage.classifications[{index}].rank_name")
            _string(item["rank_value"], f"taxonomic_coverage.classifications[{index}].rank_value")

    for index, item in enumerate(_list(metadata.get("bibliography", []), "bibliography")):
        item = _mapping(item, f"bibliography[{index}]")
        _required(item, f"bibliography[{index}]", "text", "identifier")
        _string(item["text"], f"bibliography[{index}].text")
        _string(item["identifier"], f"bibliography[{index}].identifier")

    for index, item in enumerate(_list(metadata.get("external_datasets", []), "external_datasets")):
        item = _mapping(item, f"external_datasets[{index}]")
        _required(item, f"external_datasets[{index}]", "name", "character_encoding", "format_name", "format_version", "function", "url")
        for key in ("name", "character_encoding", "format_name", "function"):
            _string(item[key], f"external_datasets[{index}].{key}")
        _string(item["format_version"], f"external_datasets[{index}].format_version", allow_empty=True)
        _url(item["url"], f"external_datasets[{index}].url")

    if "collection" in metadata:
        collection = _mapping(metadata["collection"], "collection")
        _required(collection, "collection", "parent_identifier", "identifier", "name")
        for key in ("parent_identifier", "identifier", "name"):
            _string(collection[key], f"collection.{key}", allow_empty=True)

    if "resource_logo_url" in metadata:
        _url(metadata["resource_logo_url"], "resource_logo_url")
    for key in ("preservation_methods",):
        for index, item in enumerate(_list(metadata.get(key, []), key)):
            _string(item, f"{key}[{index}]")
    if "gbif_metadata" in metadata:
        gbif = _mapping(metadata["gbif_metadata"], "gbif_metadata")
        _required(gbif, "gbif_metadata", "hierarchy_level", "citation")
        _string(gbif["hierarchy_level"], "gbif_metadata.hierarchy_level")
        citation = _mapping(gbif["citation"], "gbif_metadata.citation")
        _required(citation, "gbif_metadata.citation", "text", "identifier")
        _string(citation["text"], "gbif_metadata.citation.text")
        _string(
            citation["identifier"],
            "gbif_metadata.citation.identifier",
            allow_empty=True,
        )
