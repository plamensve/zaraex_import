"""Regression checks for linked NRA address catalogues and XML safety."""
import unittest
from addresses import LOCATIONS as BASE_LOCATIONS, CITY_MUNICIPALITIES as BASE_CITY_MUNICIPALITIES
from nap_stay.location_selector import (
    LOCATIONS, CITY_MUNICIPALITIES, available_locations, resolve_location,
    choice_label, validate_location_codes,
)


class StayLocationsTests(unittest.TestCase):
    def test_both_modules_use_identical_catalogues(self):
        self.assertEqual(LOCATIONS, BASE_LOCATIONS)
        self.assertEqual(CITY_MUNICIPALITIES, BASE_CITY_MUNICIPALITIES)

    def test_sofia_capital_is_separate_from_sofia_region(self):
        choices = available_locations("municipality", "SOF")
        self.assertEqual(choices, [{"name": "Столична", "code": "SOF46"}])
        self.assertEqual(resolve_location(choices, "София")["code"], "SOF46")
        self.assertNotIn(choices[0], available_locations("municipality", "SFO"))
        self.assertIn({"name": "гр.София", "code": "68134"}, available_locations("city", "SOF", "SOF46"))
        validate_location_codes("SOF", "SOF46", "68134")

    def test_duplicate_settlement_names_keep_their_codes(self):
        choices = [item for item in LOCATIONS["city"] if item["name"] == "с.Бяла река"]
        self.assertGreater(len(choices), 1)
        self.assertIsNone(resolve_location(choices, "с.Бяла река"))
        for item in choices:
            self.assertEqual(resolve_location(choices, choice_label(item)), item)
            self.assertEqual(resolve_location(choices, item["name"], item["code"]), item)
            municipality = CITY_MUNICIPALITIES[item["code"]]
            self.assertIn(item, available_locations("city", municipality[:3], municipality))

    def test_children_require_a_parent_and_only_include_confirmed_links(self):
        self.assertEqual(available_locations("municipality"), [])
        self.assertEqual(available_locations("city"), [])
        for item in LOCATIONS["municipality"]:
            choices = available_locations("city", item["code"][:3], item["code"])
            self.assertTrue(all(CITY_MUNICIPALITIES[city["code"]] == item["code"] for city in choices))

    def test_mismatched_address_codes_rejected(self):
        for address in (("SFO", "SOF46", "68134"), ("SOF", "SOF46", "07598"),
                        ("SOF", "VAR05", "07598"), ("BAD", "SOF46", "68134")):
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate_location_codes(*address)


if __name__ == "__main__":
    unittest.main()
