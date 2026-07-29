import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from dwca_config import (
    ConfigError,
    MetadataValidationError,
    collection_names,
    load_collection,
    load_default,
    load_eml_config,
    merge_config,
    normalize_eml_metadata,
    render_eml,
    validate_metadata,
)
from dwca_config.eml import flatten_eml, merge_eml, parse_eml


FIXTURES = Path(__file__).parent / "fixtures" / "eml"


def fixture_metadata(name):
    return flatten_eml(
        parse_eml((FIXTURES / f"{name}.xml").read_text(encoding="utf-8"))
    )


class ConfigTests(unittest.TestCase):
    def test_every_packaged_collection_loads_through_public_api(self):
        self.assertEqual(collection_names(), tuple(sorted(collection_names())))
        for name in collection_names():
            with self.subTest(name=name):
                config = load_collection(name)
                validate_metadata(config["dwca_metadata"])
                self.assertIn("title", config["dwca_metadata"])
                self.assertNotIn("datasetTitle", config["dwca_metadata"])

    def test_collection_merging_and_fresh_values(self):
        config = load_collection("birds")
        self.assertEqual(config["dwca_defaults"]["institutionCode"], "BBM")
        self.assertEqual(config["dwca_defaults"]["collectionCode"], "CTC")
        for name in (
            "birds",
            "entomology",
            "fish",
            "fossils",
            "lichen",
            "marine_invertebrates",
        ):
            with self.subTest(retired_query_collection=name):
                self.assertIsNone(load_collection(name)["query_id"])
        first = load_collection("vascular")
        second = load_collection("vascular")
        first["dwca_metadata"]["creators"][0]["given_name"] = "changed"
        self.assertNotEqual(
            first["dwca_metadata"]["creators"],
            second["dwca_metadata"]["creators"],
        )
        default = load_default()
        default["dwca_defaults"]["institutionCode"] = "changed"
        self.assertEqual(load_default()["dwca_defaults"]["institutionCode"], "BBM")

    def test_merge_does_not_mutate_inputs(self):
        base = {"nested": {"left": 1}}
        override = {"nested": {"right": 2}}
        original = deepcopy(base)
        self.assertEqual(
            merge_config(base, override),
            {"nested": {"left": 1, "right": 2}},
        )
        self.assertEqual(base, original)

    def test_vascular_metadata_is_complete(self):
        metadata = load_collection("vascular")["dwca_metadata"]
        self.assertGreaterEqual(len(metadata["associated_parties"]), 4)
        self.assertEqual(len(metadata["keyword_sets"]), 4)
        self.assertEqual(metadata["license"]["identifier"], "CC0-1.0")
        self.assertEqual(len(metadata["distributions"]), 2)
        self.assertEqual(len(metadata["bibliography"]), 4)
        self.assertEqual(metadata["collection"]["identifier"], "UBC")
        self.assertEqual(
            metadata["taxonomic_coverage"]["classifications"][0]["rank_value"],
            "Plantae",
        )
        self.assertIn("citation", metadata["gbif_metadata"])

    def test_algae_metadata_is_complete(self):
        metadata = load_collection("algae")["dwca_metadata"]
        self.assertEqual(len(metadata["associated_parties"]), 5)
        self.assertEqual(len(metadata["keyword_sets"]), 4)
        self.assertEqual(len(metadata["distributions"]), 2)
        self.assertEqual(len(metadata["external_datasets"]), 3)
        self.assertEqual(len(
            metadata["taxonomic_coverage"]["classifications"]
        ), 7)
        self.assertEqual(metadata["formation_period"], "mid 1800s-present")
        self.assertEqual(metadata["collection"]["name"], metadata["title"])

    def test_legacy_normalization_preserves_every_value(self):
        defaults = load_default()
        shared = defaults["eml_metadata"]
        for name in collection_names():
            with self.subTest(name=name):
                raw = load_collection(name, merged=False)
                legacy = merge_eml(shared, raw.get("eml_metadata", {}))
                canonical = normalize_eml_metadata(
                    legacy,
                    dataset_id=raw.get("dwca_defaults", {}).get("datasetID")
                    or legacy["alternateIdentifiers"][0],
                )
                flattened_values = repr(canonical)
                for key in (
                    "associatedParties", "keywordSets", "geographicCoverage",
                    "license", "distributions", "externalDataSets",
                    "collection", "gbifMetadata",
                ):
                    if key in legacy:
                        self.assertIn(repr(
                            normalize_eml_metadata(
                                {
                                    "datasetTitle": legacy["datasetTitle"],
                                    "abstract": legacy["abstract"],
                                    "languageCode": legacy["languageCode"],
                                    "creators": legacy["creators"],
                                    "metadataProviders": legacy["metadataProviders"],
                                    "contacts": legacy["contacts"],
                                    "intellectualRights": legacy["intellectualRights"],
                                    "alternateIdentifiers": legacy["alternateIdentifiers"],
                                    "publicationDate": legacy["publicationDate"],
                                    key: legacy[key],
                                },
                                dataset_id=canonical["dataset_id"],
                            ).get({
                                "associatedParties": "associated_parties",
                                "keywordSets": "keyword_sets",
                                "geographicCoverage": "geographic_coverage",
                                "license": "license",
                                "distributions": "distributions",
                                "externalDataSets": "external_datasets",
                                "collection": "collection",
                                "gbifMetadata": "gbif_metadata",
                            }[key])),
                            flattened_values,
                        )

    def test_packaged_legacy_data_reconstructs_curated_snapshots(self):
        for name in collection_names():
            with self.subTest(name=name):
                self.assertEqual(
                    load_collection(name)["eml_metadata"],
                    fixture_metadata(name),
                )

    def test_malformed_nested_metadata_is_rejected(self):
        cases = []
        vascular = load_collection("vascular")["dwca_metadata"]
        malformed = deepcopy(vascular)
        malformed["creators"] = "not a list"
        cases.append(malformed)
        malformed = deepcopy(vascular)
        malformed["license"].pop("url")
        cases.append(malformed)
        malformed = deepcopy(vascular)
        malformed["geographic_coverage"]["north"] = 91
        cases.append(malformed)
        malformed = deepcopy(vascular)
        malformed["distributions"][0].pop("function")
        cases.append(malformed)
        malformed = deepcopy(vascular)
        malformed["taxonomic_coverage"]["classifications"][0].pop("rank_name")
        cases.append(malformed)
        malformed = deepcopy(load_collection("algae")["dwca_metadata"])
        malformed["external_datasets"][0].pop("url")
        cases.append(malformed)
        for metadata in cases:
            with self.subTest(case=len(cases)):
                with self.assertRaises(MetadataValidationError):
                    validate_metadata(metadata)

    def test_load_eml_config_is_canonical_and_independent(self):
        first = load_eml_config("vascular")
        self.assertEqual(first, load_collection("vascular")["dwca_metadata"])
        first["title"] = "changed"
        self.assertNotEqual(first["title"], load_eml_config("vascular")["title"])

    def test_deprecated_legacy_alias_is_retained(self):
        config = load_collection("algae")
        self.assertEqual(config["eml_metadata"]["datasetTitle"], config["dwca_metadata"]["title"])
        self.assertNotIn("datasetTitle", config["dwca_metadata"])

    def test_renderer_accepts_canonical_configuration(self):
        xml = render_eml(
            "vascular",
            package_id="test-package",
            publication_date="2026-07-28",
            date_stamp="2026-07-28",
        )
        root = ET.fromstring(xml)
        self.assertEqual(root.attrib["packageId"], "test-package")
        self.assertGreater(len(list(root.iter())), 100)

    def test_unknown_collection_has_useful_error(self):
        with self.assertRaisesRegex(ConfigError, "Unknown collection"):
            load_collection("missing")


if __name__ == "__main__":
    unittest.main()
