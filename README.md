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
example `v0.1.0`. Do not use a moving branch such as `main` for deployments.

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

Several collection files contain `null` placeholders for values such as
`specify_name`, `query_id`, `deduplicate_by`, or EML descriptions. A consumer
must not enable an affected collection until its required values are complete.

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
merging, independent return values, and invalid collection names.


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
