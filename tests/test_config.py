import unittest

from dwca_config import (
    ConfigError,
    collection_names,
    load_collection,
    load_default,
    merge_config,
)


class ConfigTests(unittest.TestCase):
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

    def test_unknown_collection_has_useful_error(self):
        with self.assertRaisesRegex(ConfigError, "Unknown collection"):
            load_collection("../birds")


if __name__ == "__main__":
    unittest.main()
