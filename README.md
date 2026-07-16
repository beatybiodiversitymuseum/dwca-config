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

`default.yaml` contains shared source-heading aliases, DwCA publication
defaults, EML defaults, and media policy. Each collection file is recursively
merged over that default and contains only additions or overrides.

Mappings are intentionally many-to-one. An exporter should consider only source
headings present in the downloaded CSV. When several present headings map to the
same Darwin Core term, coalesce them in YAML order: fill empty values from later
aliases and fail validation if two aliases contain conflicting non-empty values
for one record.

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
