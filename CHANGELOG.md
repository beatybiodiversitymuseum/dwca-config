# Changelog

## v0.3.0 — 2026-07-28

### Fixed

- Corrected the preferred-taxon rank path so `taxonRank` is read from the
  infraspecific taxon node.

## v0.2.0 — 2026-07-23

This release makes the package the maintained source of Beaty Biodiversity
Museum DwCA and EML publication configuration.

### Added

- Published metadata for twelve Beaty collections, including fungi and
  herpetology.
- Readable, shared `eml_metadata` configuration reconstructed from the
  published Canadensys EML documents.
- `load_eml_config()` for resolved EML metadata.
- `render_eml()` for generating escaped, standalone GBIF-profile EML documents.
- A packaged EML outline, curated XML reference fixtures, and an EML import
  utility.

### Changed

- Shared non-conflicting Darwin Core mappings now live in `default.yaml`;
  collection files contain only genuine mapping conflicts.
- Media settings and incomplete operational fields now inherit shared defaults.
- Every collection deduplicates by catalogue number, with a source-specific
  Bryophytes override.
- EML-derived title, description, and organization values no longer need to be
  duplicated under `dwca_metadata`.
- Publisher-owned UUIDs, versions, dates, and replacement state are generated
  at publication time instead of being maintained as configuration.
- Legacy biodiversity-informatics contact details were replaced with Paul
  Bucci's current details.

### Verification

- All twelve collection configurations load and render as well-formed EML.
- The 21-test suite passes.
- Both the source distribution and wheel build successfully.
# 0.4.1

- Remove the obsolete entomology Specify query ID so consumers do not run the
  retired saved query.

# 0.4.0

- Make `dwca_metadata` the complete, validated snake_case EML metadata contract.
- Preserve all curated IPT metadata, including alternate identifiers, download
  distributions, publication-date policy, and GBIF citations.
- Retain `eml_metadata` temporarily as a deprecated camelCase compatibility
  alias.
