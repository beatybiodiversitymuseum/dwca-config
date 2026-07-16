# DwCA configuration

Institution-wide Darwin Core Archive publication configuration for the Beaty
Biodiversity Museum. This repository contains data and policy only; exporters
and download services consume it from their own repositories.

## Layout

```text
default.yaml
collections/
  algae.yaml
  birds.yaml
  bryophytes.yaml
  entomology.yaml
  fish.yaml
  fossils.yaml
  mammals.yaml
  marine_invertebrates.yaml
  vascular.yaml
```

`default.yaml` contains shared canonical Specify-path mappings, DwCA publication
defaults, EML defaults, and media policy. Each collection file is recursively
merged over that default and contains only additions or overrides.

Specify mappings use readable structural keys derived from each saved query's
base table, relationships, terminal field, and tree rank, for example
`collectionobject.collectingEvent.locality.geography.Country.fullName`. They do
not depend on localized CSV headings. Mappings are intentionally many-to-one.
An exporter should consider only structural keys present in the saved query.
When several present keys map to the same Darwin Core term, coalesce them in YAML
order: fill empty values from later sources and fail validation if two sources
contain conflicting non-empty values for one record.

Non-Specify sources, currently Bryophytes from Symbiota, require their own
source-column mapping rather than the structural Specify defaults.

## Incomplete collections

Several collection files contain `null` placeholders for `specify_name`,
`query_id`, `deduplicate_by`, or EML descriptions. They must not be enabled by a
consumer until their required values are filled in. Bryophytes is currently
marked as a Symbiota source rather than a Specify saved query.

Marine-invertebrate measurement fields remain under `dwca_extensions` until an
appropriate extension namespace and terms are selected.

## Consumer contract

Consumers should receive the checkout path through `DWCA_CONFIG_DIR`, load
`default.yaml`, and merge the selected `collections/<name>.yaml` over it. Runtime
parameters and credentials do not belong in this repository.

Production consumers should pin this repository to a reviewed Git commit or
release tag rather than automatically following its default branch.
