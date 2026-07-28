# DwCA configuration

## Overview

This internal Python package contains the institution-wide Darwin Core Archive
(DwCA) publication configuration for the Beaty Biodiversity Museum. Exporters
and download services install the package and load collection configuration
through its Python API.

The package supports Python 3.9 and newer. It is not published to PyPI, so
installers need access to the private
`beatybiodiversitymuseum/dwca-config` GitHub repository and an authorized SSH
key.

## Installation

Applications should install a reviewed release tag:

```console
python -m pip install "dwca-config @ git+ssh://git@github.com/beatybiodiversitymuseum/dwca-config.git@<release-tag>"
```

Declare the same pinned dependency in the consuming application's
`pyproject.toml`:

```toml
[project]
dependencies = [
  "dwca-config @ git+ssh://git@github.com/beatybiodiversitymuseum/dwca-config.git@<release-tag>",
]
```

Replace `<release-tag>` with the release required by the application, for
example `v0.4.0`. Do not use a moving branch such as `main` for deployments.

If installation cannot authenticate with GitHub, verify the SSH connection:

```console
ssh -T git@github.com
```

## Usage

Load a collection with the institution defaults recursively merged beneath its
collection-specific values:

```python
from dwca_config import load_collection

config = load_collection("birds")
```

The public API is:

- `collection_names()` — return available collection names in sorted order.
- `load_collection(name)` — return a fresh, merged collection configuration.
- `load_collection(name, merged=False)` — return only the collection overrides.
- `load_default()` — return a fresh copy of the institution defaults.
- `load_eml_config(name)` — return a fresh copy of the same canonical
  `dwca_metadata` contract.
- `render_eml(name, **publishing_state)` — generate a standalone, escaped
  GBIF-profile EML document; package UUID and publication dates are generated
  when omitted.
- `merge_config(base, override)` — recursively merge mappings without mutating
  either input.

To verify an installation:

```console
python -c "from dwca_config import collection_names; print(collection_names())"
```

## Configuration model

The packaged configuration is organized as follows:

```text
src/dwca_config/
  config.py
  data/
    default.yaml
    collections/
      algae.yaml
      birds.yaml
      ...
```

`default.yaml` contains shared canonical Specify-path mappings, DwCA publication
defaults, EML defaults, and media policy. Each collection file contains only
additions or overrides and is recursively merged over the defaults by
`load_collection()`.

`load_collection(name)["dwca_metadata"]` is the one canonical public EML
contract. It is complete, recursively independent between calls, snake_case,
and validated before it is returned. Consumers never need to merge metadata
mappings or translate IPT-era names.

The package currently retains `config["eml_metadata"]` as a deprecated,
read-only compatibility alias using the old camelCase vocabulary. New code must
not use it. It will be removed in a future breaking release. The packaged YAML
continues to use that source vocabulary temporarily so existing data can be
compared exactly with the curated IPT snapshots; normalization is centralized
inside this package.

### Canonical EML schema

The complete public structure is:

```text
dwca_metadata
├── dataset_id: string (required)
├── alternate_identifiers: list[string] (required)
├── title: string (required)
├── description: string (required)
├── language: string (required)
├── creators: list[party] (required, non-empty)
├── metadata_providers: list[party] (required)
├── associated_parties: list[party]
├── contacts: list[party] (required, non-empty)
├── publication_date: {automatic: true} | {automatic: false, value: YYYY-MM-DD}
├── intellectual_rights: {text, link?: {url, title}} (required)
├── license?: {name, url, identifier}
├── keyword_sets?: list[{keywords: list[string], thesaurus: string}]
├── distributions?: list[{scope, function, url}]
├── maintenance?: {description, frequency}
├── geographic_coverage?: {description, west, east, north, south}
├── taxonomic_coverage?: {
│     description,
│     classifications: list[{rank_name, rank_value, common_name?}]
│   }
├── temporal_coverage?: {begin_date, end_date}
├── methods?: {steps: list[string]}
├── project?: object
├── additional_info?: string
├── bibliography?: list[{text, identifier}]
├── external_datasets?: list[{
│     name, character_encoding, format_name, format_version, function, url
│   }]
├── resource_logo_url?: URL
├── collection?: {parent_identifier, identifier, name}
├── formation_period?: string
├── preservation_methods?: list[string]
├── curatorial_units?: list[{
│     unit_type, units?, uncertainty?, begin_range?, end_range?
│   }]
└── gbif_metadata?: {
      hierarchy_level,
      citation: {text, identifier}
    }

party = {
  given_name?, sur_name?, organization_name?, position_name?, phone?, email?,
  online_url?, role?,
  address?: {
    delivery_point?, city?, administrative_area?, postal_code?, country?
  },
  user_id?: {value, directory}
}
```

Required nested keys are validated, as are list/scalar distinctions, absolute
HTTP(S) URLs, ISO publication dates, and coordinate ranges. Longitudes must be
between -180 and 180, latitudes between -90 and 90, west must not exceed east,
and south must not exceed north.

### Legacy key migration

Top-level IPT-era keys map as follows:

| Legacy | Canonical |
|---|---|
| `datasetTitle` | `title` |
| `alternateIdentifiers` | `alternate_identifiers` |
| `abstract` | `description` |
| `languageCode` | `language` |
| `metadataProviders` | `metadata_providers` |
| `associatedParties` | `associated_parties` |
| `publicationDate` | `publication_date` |
| `keywordSets` | `keyword_sets` |
| `intellectualRights` | `intellectual_rights` |
| `geographicCoverage` | `geographic_coverage` |
| `taxonomicCoverage` | `taxonomic_coverage` |
| `temporalCoverage` | `temporal_coverage` |
| `additionalInfo` | `additional_info` |
| `externalDataSets` | `external_datasets` |
| `resourceLogoUrl` | `resource_logo_url` |
| `formationPeriod` | `formation_period` |
| `preservationMethods` | `preservation_methods` |
| `curatorialUnits` | `curatorial_units` |
| `gbifMetadata` | `gbif_metadata` |

All nested camelCase keys are converted recursively (`givenName` to
`given_name`, `rankValue` to `rank_value`, and so on). `dataset_id` comes from
the collection's publication default and falls back to its first alternate
identifier. Unrecognized legacy fields are retained under their recursively
snake-cased names rather than silently discarded.

### Usage

```python
from dwca_config import load_collection

metadata = load_collection("vascular")["dwca_metadata"]

title = metadata["title"]
doi = metadata["dataset_id"]
creator = metadata["creators"][0]["organization_name"]
license_url = metadata["license"]["url"]
bounds = metadata["geographic_coverage"]
gbif_citation = metadata["gbif_metadata"]["citation"]
```

That single mapping contains every maintained value required to construct the
GBIF-profile EML. XML generation remains the consumer's responsibility;
`render_eml()` is retained only as the package's existing convenience renderer.

The corresponding human-readable XML outline is packaged at
`templates/eml.xml.j2`. The supported renderer builds repeated and optional
sections from the same vocabulary:

```python
from dwca_config import render_eml

xml = render_eml(
    "algae",
    package_id="90302970-1bc6-4865-be76-9aef1dd707f9",
    publication_date="2026-07-23",
    date_stamp="2026-07-23",
)
```

Values are XML-escaped, absent optional sections are omitted, and generated
publisher state can be explicitly supplied for reproducible output.

To write the generated document:

```python
from pathlib import Path

Path("eml.xml").write_text(xml, encoding="utf-8")
```

Mutable publisher state such as package versions, date stamps, `dc:replaces`,
system, and scope remains excluded. The contract does include stable alternate
identifiers, archive distributions, GBIF citation metadata, hierarchy level,
and an explicit publication-date policy. `{automatic: true}` directs a consumer
to use its current publication date.

Curated XML reference snapshots live under `tests/fixtures/eml`; they are not
included in the runtime package. They seed the importer and verify that every
maintained semantic value is represented in YAML. Re-import the maintained
fields after replacing any fixtures:

```console
PYTHONPATH=src python scripts/import_eml.py
```

Specify mappings use structural keys derived from each saved query's base table,
relationships, terminal field, and tree rank, for example:

```text
collectionobject.collectingEvent.locality.geography.Country.fullName
```

These keys do not depend on localized CSV headings. Mappings are intentionally
many-to-one. Consumers should consider only structural keys present in the saved
query. When multiple present keys map to one Darwin Core term, coalesce them in
YAML order: fill empty values from later sources and fail validation when a
record contains conflicting non-empty values.

Non-Specify sources require their own source-column mappings. Bryophytes is
currently sourced from Symbiota rather than a Specify saved query.

Runtime parameters, credentials, and secrets do not belong in this package.

## Incomplete collections

Loading a configuration does not mean that a collection is ready to publish.
Consumers must validate every field required by their workflow.

The shared defaults resolve unspecified `specify_name` and `query_id` values to
`null`. Deduplication defaults to the Specify catalog-number path; non-Specify
sources override it with their catalog-number column. A consumer must not enable
an affected collection until every field required by its workflow is complete.

Marine-invertebrate measurement fields remain under `dwca_extensions` until an
appropriate extension namespace and terms are selected.

## Releasing a new version

1. Update the package version in both `pyproject.toml` and
   `src/dwca_config/__init__.py`.
2. Run the tests and build both distribution formats:

   ```console
   python -m pip install build
   python -m unittest discover -s tests -v
   python -m build
   ```

3. Review and merge the changes to `main`.
4. Tag the reviewed merge commit with the matching version and push the tag:

   ```console
   git tag -a v0.2.0 -m "dwca-config v0.2.0"
   git push origin v0.2.0
   ```

5. Update consuming applications to the new tag only after reviewing the
   configuration changes.

Replace `v0.2.0` with the version being released. Existing release tags must
not be moved or reused.

## Development and tests

Clone the repository and install it in editable mode:

```console
git clone git@github.com:beatybiodiversitymuseum/dwca-config.git
cd dwca-config
python -m pip install -e .
```

Run the test suite:

```console
python -m unittest discover -s tests -v
```

Tests cover packaged-resource discovery, loading every collection, recursive
merging, shared-versus-collection override boundaries, reconstruction of the
published EML metadata, generation of standalone EML for every collection, XML
escaping, independent return values, and invalid collection names.


## Agent integration prompt

Replace the placeholders and give the following prompt to a coding agent:

```text
Integrate the internal `dwca-config` Python package into this application.

Follow the installation and consumer guidance in:
https://github.com/beatybiodiversitymuseum/dwca-config

Use collection `<COLLECTION_NAME>` and pin the dependency to
`<RELEASE_TAG>`. Load configuration through
`dwca_config.load_collection()`, validate every field required by this
application, and add tests for the integration. Do not copy or parse the
package's YAML resources directly.

Before finishing, run the relevant tests and report the exact `dwca-config`
release tag used.
```
