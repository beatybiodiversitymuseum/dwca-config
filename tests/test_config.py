import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from dwca_config import (
    ConfigError,
    collection_names,
    load_collection,
    load_default,
    load_eml_config,
    merge_config,
    render_eml,
)
from dwca_config.eml import EML_KEY_ORDER, flatten_eml, parse_eml

EML_FIXTURES = Path(__file__).parent / "fixtures" / "eml"


def load_eml_fixture(name):
    return (EML_FIXTURES / f"{name}.xml").read_text(encoding="utf-8")


class ConfigTests(unittest.TestCase):
    def assert_key_order(self, mapping, canonical):
        positions = {key: index for index, key in enumerate(canonical)}
        actual = [key for key in mapping if key in positions]
        self.assertEqual(actual, sorted(actual, key=positions.get))

    def test_packaged_collections_are_discoverable(self):
        names = collection_names()
        self.assertIn("birds", names)
        self.assertIn("marine_invertebrates", names)
        self.assertEqual(names, tuple(sorted(names)))

    def test_every_packaged_collection_loads(self):
        for name in collection_names():
            with self.subTest(name=name):
                self.assertEqual(load_collection(name, merged=False)["name"], name)

    def test_collection_is_recursively_merged_over_defaults(self):
        config = load_collection("birds")
        self.assertEqual(config["name"], "birds")
        self.assertEqual(config["dwca_defaults"]["collectionCode"], "CTC")
        self.assertEqual(config["dwca_defaults"]["institutionCode"], "BBM")
        self.assertEqual(
            config["dwca_terms"]["collectionobject.catalogNumber"],
            "catalogNumber",
        )

    def test_media_and_incomplete_operational_fields_have_shared_defaults(self):
        algae = load_collection("algae")
        self.assertEqual(
            algae["media"]["attachment_column"],
            "collectionobject.collectionObjectAttachments",
        )
        self.assertNotIn("media", load_collection("algae", merged=False))

        fungi = load_collection("fungi")
        self.assertIsNone(fungi["specify_name"])
        self.assertIsNone(fungi["query_id"])
        self.assertEqual(
            fungi["deduplicate_by"],
            "collectionobject.catalogNumber",
        )
        raw_fungi = load_collection("fungi", merged=False)
        self.assertNotIn("specify_name", raw_fungi)
        self.assertNotIn("query_id", raw_fungi)
        self.assertNotIn("deduplicate_by", raw_fungi)

        for name in collection_names():
            with self.subTest(deduplicate_collection=name):
                self.assertTrue(
                    load_collection(name)["deduplicate_by"].endswith(
                        "catalogNumber"
                    )
                )

    def test_only_conflicting_dwca_mappings_remain_in_collections(self):
        targets_by_source = {}
        for source, target in load_default()["dwca_terms"].items():
            targets_by_source.setdefault(source, set()).add(target)
        for name in collection_names():
            for source, target in load_collection(
                name,
                merged=False,
            ).get("dwca_terms", {}).items():
                targets_by_source.setdefault(source, set()).add(target)

        for name in collection_names():
            for source in load_collection(
                name,
                merged=False,
            ).get("dwca_terms", {}):
                with self.subTest(collection=name, source=source):
                    self.assertGreater(len(targets_by_source[source]), 1)

    def test_unmerged_collection_contains_only_overrides(self):
        config = load_collection("birds", merged=False)
        self.assertNotIn("institutionCode", config["dwca_defaults"])

    def test_loads_are_independent(self):
        first = load_default()
        first["dwca_defaults"]["institutionCode"] = "changed"
        self.assertEqual(load_default()["dwca_defaults"]["institutionCode"], "BBM")

    def test_merge_does_not_mutate_inputs(self):
        base = {"nested": {"left": 1}}
        override = {"nested": {"right": 2}}
        self.assertEqual(
            merge_config(base, override),
            {"nested": {"left": 1, "right": 2}},
        )
        self.assertEqual(base, {"nested": {"left": 1}})

    def test_herbarium_metadata_matches_published_archives(self):
        vascular = load_collection("vascular")
        algae = load_collection("algae")

        for config in (vascular, algae):
            self.assertEqual(
                config["dwca_metadata"]["organization"],
                "University of British Columbia Herbarium",
            )

        self.assertIn(
            "more than 235,000 accessioned specimens",
            vascular["dwca_metadata"]["description"],
        )
        self.assertIn(
            "over 100,000 specimens",
            algae["dwca_metadata"]["description"],
        )

    def test_additional_published_metadata_is_populated(self):
        expected = {
            "lichen": (
                "University of British Columbia Herbarium (UBC) - Lichen Collection",
                "University of British Columbia Herbarium",
            ),
            "fungi": (
                "University of British Columbia Herbarium (UBC) - Fungi Collection",
                "University of British Columbia Herbarium",
            ),
            "bryophytes": (
                "University of British Columbia Herbarium (UBC) - Bryophytes Collection",
                "University of British Columbia Herbarium",
            ),
            "mammals": (
                "Cowan Tetrapod Collection - Mammals",
                "Beaty Biodiversity Museum",
            ),
            "herpetology": (
                "Cowan Tetrapod Collection - Herpetology",
                "Beaty Biodiversity Museum",
            ),
            "birds": (
                "Cowan Tetrapod Collection - Birds",
                "Beaty Biodiversity Museum",
            ),
            "entomology": (
                "University of British Columbia - Spencer Entomological Collection (UBCZ)",
                "University of British Columbia, Beaty Biodiversity Museum",
            ),
            "marine_invertebrates": (
                "Beaty Biodiversity Museum Marine Invertebrate Collection",
                "Beaty Biodiversity Museum",
            ),
            "fossils": (
                "Beaty Biodiversity Museum Fossil Collection",
                "Beaty Biodiversity Museum",
            ),
            "fish": (
                "Beaty Biodiversity Museum Fish Collection",
                "Beaty Biodiversity Museum",
            ),
        }

        for name, (title, organization) in expected.items():
            with self.subTest(name=name):
                metadata = load_collection(name)["dwca_metadata"]
                self.assertEqual(metadata["title"], title)
                self.assertEqual(metadata["organization"], organization)
                self.assertTrue(metadata["description"])

    def test_every_linked_eml_document_is_complete_and_well_formed(self):
        for name in collection_names():
            with self.subTest(name=name):
                root = ET.fromstring(load_eml_fixture(name))
                dataset = root.find("dataset")
                self.assertIsNotNone(dataset)
                self.assertIsNotNone(dataset.find("title"))
                self.assertIsNotNone(dataset.find("creator"))
                self.assertIsNotNone(dataset.find("abstract"))
                self.assertIsNotNone(dataset.find("intellectualRights"))
                self.assertIsNotNone(root.find("additionalMetadata"))

    def test_eml_preserves_detailed_published_metadata(self):
        algae = ET.fromstring(load_eml_fixture("algae"))
        self.assertGreaterEqual(len(algae.findall("dataset/associatedParty")), 5)
        self.assertEqual(
            algae.findtext(
                "dataset/coverage/taxonomicCoverage/"
                "taxonomicClassification/taxonRankName"
            ),
            "phylum",
        )
        self.assertIsNotNone(
            algae.find("additionalMetadata/metadata/gbif/collection")
        )

    def test_normalized_eml_yaml_reconstructs_every_published_document(self):
        for name in collection_names():
            config = load_collection(name, merged=False)
            if "eml_metadata" not in config:
                continue
            with self.subTest(name=name):
                self.assertEqual(
                    load_eml_config(name),
                    flatten_eml(parse_eml(load_eml_fixture(name))),
                )

    def test_every_collection_renders_as_standalone_eml(self):
        namespace = "https://eml.ecoinformatics.org/eml-2.2.0"
        for name in collection_names():
            with self.subTest(name=name):
                xml = render_eml(
                    name,
                    package_id=f"test-{name}",
                    publication_date="2026-07-23",
                    date_stamp="2026-07-23",
                )
                root = ET.fromstring(xml)
                metadata = load_eml_config(name)
                self.assertEqual(root.tag, f"{{{namespace}}}eml")
                self.assertEqual(root.attrib["packageId"], f"test-{name}")
                self.assertEqual(
                    root.findtext("dataset/title"),
                    metadata["datasetTitle"],
                )
                self.assertEqual(
                    len(root.findall("dataset/creator")),
                    len(metadata["creators"]),
                )
                self.assertEqual(
                    len(root.findall("dataset/contact")),
                    len(metadata["contacts"]),
                )
                self.assertIsNotNone(
                    root.find("additionalMetadata/metadata/gbif/dateStamp")
                )

    def test_eml_renderer_escapes_yaml_values(self):
        from dwca_config.eml import render_eml_document

        xml = render_eml_document(
            {
                "datasetTitle": "Fish & algae <specimens>",
                "creators": [{"organizationName": "A & B"}],
                "abstract": "An <escaped> & safe abstract",
                "contacts": [{"email": "test@example.org"}],
            },
            package_id="escaping-test",
            publication_date="2026-07-23",
            date_stamp="2026-07-23",
        )
        root = ET.fromstring(xml)
        self.assertEqual(
            root.findtext("dataset/title"),
            "Fish & algae <specimens>",
        )

    def test_eml_yaml_inherits_shared_metadata(self):
        fossils_override = load_collection("fossils", merged=False)["eml_metadata"]
        self.assertNotIn("languageCode", fossils_override)
        self.assertNotIn("metadataProviders", fossils_override)
        fossils = load_eml_config("fossils")
        self.assertEqual(fossils["languageCode"], "eng")
        self.assertEqual(
            fossils["metadataProviders"][0]["email"],
            "paul.bucci@ubc.ca",
        )
        self.assertIn("intellectualRights", fossils)

    def test_compatibility_metadata_is_derived_without_yaml_duplicates(self):
        for name in collection_names():
            raw = load_collection(name, merged=False)
            if "eml_metadata" not in raw:
                continue
            with self.subTest(name=name):
                self.assertNotIn("dwca_metadata", raw)
                if name != "entomology":
                    self.assertNotIn("datasetName", raw["dwca_defaults"])

                resolved = load_collection(name)
                title = resolved["eml_metadata"]["datasetTitle"]
                self.assertEqual(resolved["dwca_metadata"]["title"], title)
                if name == "entomology":
                    self.assertNotEqual(
                        resolved["dwca_defaults"]["datasetName"],
                        title,
                    )
                else:
                    self.assertEqual(
                        resolved["dwca_defaults"]["datasetName"],
                        title,
                    )

    def test_paul_bucci_replaces_legacy_informatics_contact(self):
        legacy_values = (
            "Ma" + "rk",
            "Pit" + "blado",
            "mark.pitblado" + "@ubc.ca",
            "0000-0002-" + "8786-5167",
            "Curator of " + "Informatics",
            "2122 Main" + " Mall",
        )
        for name in collection_names():
            with self.subTest(name=name):
                serialized = (
                    repr(load_collection(name)) + load_eml_fixture(name)
                )
                for value in legacy_values:
                    self.assertNotIn(value, serialized)

        default_provider = load_default()["eml_metadata"]["metadataProviders"][0]
        self.assertEqual(default_provider["givenName"], "Paul")
        self.assertEqual(default_provider["surName"], "Bucci")
        self.assertEqual(default_provider["email"], "paul.bucci@ubc.ca")
        self.assertEqual(
            default_provider["userId"]["value"],
            "0000-0002-8646-7730",
        )

    def test_collection_yaml_uses_canonical_key_order(self):
        collection_order = (
            "name",
            "source",
            "specify_name",
            "query_id",
            "deduplicate_by",
            "media",
            "dwca_terms",
            "dwca_defaults",
            "dwca_extensions",
            "eml_metadata",
        )
        default_order = (
            "collectionCode",
            "collectionID",
            "datasetID",
            "datasetName",
        )
        for name in collection_names():
            with self.subTest(name=name):
                raw = load_collection(name, merged=False)
                self.assert_key_order(raw, collection_order)
                self.assert_key_order(raw.get("dwca_defaults", {}), default_order)
                self.assert_key_order(
                    raw.get("eml_metadata", {}),
                    EML_KEY_ORDER,
                )

    def test_publishing_state_is_not_maintained_in_config(self):
        generated = {
            "packageId",
            "system",
            "scope",
            "alternateIdentifiers",
            "publicationDate",
            "dateStamp",
            "hierarchyLevel",
            "citation",
            "replaces",
        }
        for name in collection_names():
            with self.subTest(name=name):
                eml = load_eml_config(name)
                self.assertFalse(generated.intersection(eml))
                self.assertTrue(
                    all(
                        distribution.get("function") != "download"
                        for distribution in eml.get("distributions", [])
                    )
                )

    def test_unknown_collection_has_useful_error(self):
        with self.assertRaisesRegex(ConfigError, "Unknown collection"):
            load_collection("../birds")


if __name__ == "__main__":
    unittest.main()
