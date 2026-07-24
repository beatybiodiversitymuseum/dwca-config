"""Import normalized EML into the main configuration YAML files."""

from pathlib import Path
import sys

import yaml

from dwca_config.eml import (
    common_eml_template,
    eml_override,
    flatten_eml,
    parse_eml,
)


def _replace_eml_mapping(path: Path, eml: dict) -> None:
    """Replace the final top-level EML block without reformatting other YAML."""

    source = path.read_text(encoding="utf-8")
    marker = "\neml_metadata:\n"
    prefix = source.split(marker, 1)[0].rstrip() if marker in source else source.rstrip()
    rendered = yaml.safe_dump(
        {"eml_metadata": eml},
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )
    path.write_text(f"{prefix}\n{rendered}", encoding="utf-8")


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    data = repository / "src/dwca_config/data"
    root = repository / "tests/fixtures/eml"
    documents = {
        path.stem: flatten_eml(
            parse_eml(path.read_text(encoding="utf-8"))
        )
        for path in sorted(root.glob("*.xml"))
    }
    shared = common_eml_template(documents.values())

    default_path = data / "default.yaml"
    _replace_eml_mapping(default_path, shared)

    for name, document in documents.items():
        collection_path = data / "collections" / f"{name}.yaml"
        _replace_eml_mapping(
            collection_path,
            eml_override(shared, document),
        )


if __name__ == "__main__":
    sys.exit(main())
