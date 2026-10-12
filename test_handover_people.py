"""Unit tests for handover personnel records and base-dependent name suggestions."""

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import DataStore, ZaraExApp
from handover_people import (
    handover_full_name, matching_handover_people, validate_handover_person
)
from settings_editor import prepare_settings_edit, apply_settings_edit


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "bases": [{"name": "База София"}, {"name": "База Варна"}],
            "handover_people": [],
        }

    def person(self, base="База София", middle=""):
        return {
            "first_name": "Иван", "middle_name": middle,
            "last_name": "Петров", "egn": "0012345678", "base_name": base,
        }

    def test_optional_middle_name_and_egn_leading_zeros(self):
        result = validate_handover_person(self.data, self.person())
        self.assertEqual(handover_full_name(result), "Иван Петров")
        self.assertEqual(result["middle_name"], "")
        self.assertEqual(result["egn"], "0012345678")
        full = validate_handover_person(self.data, self.person(middle="Георгиев"))
        self.assertEqual(handover_full_name(full), "Иван Георгиев Петров")

    def test_requires_names_egn_and_existing_base(self):
        for field, invalid in (
            ("first_name", ""), ("last_name", ""), ("egn", "01234"),
            ("egn", "123456789X"), ("egn", "１２３４５６７８９０"),
            ("base_name", "Несъществуваща база"),
        ):
            with self.subTest(field=field, invalid=invalid):
                person = self.person()
                person[field] = invalid
                with self.assertRaises(ValueError):
                    validate_handover_person(self.data, person)

    def test_duplicate_name_or_egn_in_same_base_rejected(self):
        self.data["handover_people"].append(self.person())
        other_egn = self.person()
        other_egn["first_name"] = "Петър"
        with self.assertRaises(ValueError):
            validate_handover_person(self.data, other_egn)
        other_name = self.person()
        other_name["egn"] = "1234567890"
        with self.assertRaises(ValueError):
            validate_handover_person(self.data, other_name)
        self.assertEqual(
            validate_handover_person(self.data, self.person(base="База Варна"))["egn"],
            "0012345678",
        )

    def test_suggestions_only_include_matching_base_and_partial_names(self):
        first = self.person(middle="Георгиев")
        second = {"first_name": "Петър", "middle_name": "", "last_name": "Димитров",
                  "egn": "1111111111", "base_name": "База София"}
        outside = self.person(base="База Варна")
        self.data["handover_people"] = [outside, second, first]
        matches = matching_handover_people(self.data["handover_people"], "База София")
        self.assertEqual([handover_full_name(p) for p in matches],
                         ["Иван Георгиев Петров", "Петър Димитров"])
        self.assertEqual(matching_handover_people(
            self.data["handover_people"], "База София", "ГЕОРГ"
        ), [first])
        self.assertEqual(matching_handover_people(
            self.data["handover_people"], "База Варна", "Петър"
        ), [])

    def test_edit_validates_and_base_rename_updates_relationship(self):
        self.data["handover_people"].append(self.person())
        result = prepare_settings_edit(
            self.data, "handover_people", 0,
            {"middle_name": "Иванов", "egn": "0012345678"}
        )
        apply_settings_edit(self.data, "handover_people", 0, result)
        self.assertEqual(handover_full_name(self.data["handover_people"][0]),
                         "Иван Иванов Петров")
        apply_settings_edit(self.data, "bases", 0, {"name": "База София - нова"})
        self.assertEqual(self.data["handover_people"][0]["base_name"], "База София - нова")

    def test_selection_populates_egn_and_base_change_clears_details(self):
        self.data["handover_people"] = [self.person(), self.person(base="База Варна")]
        widget = {}
        subject = SimpleNamespace(
            store=SimpleNamespace(data=self.data),
            base_var=Variable("База София"),
            handover_name_var=Variable("Иван Петров"),
            handover_egn_var=Variable(""),
            handover_name_combo=widget,
        )
        subject.refresh_handover_dropdowns = lambda query="": ZaraExApp.refresh_handover_dropdowns(subject, query)
        subject.update_selection_info = Mock()
        ZaraExApp.refresh_handover_dropdowns(subject)
        self.assertEqual(widget["values"], ["Иван Петров"])
        ZaraExApp.on_handover_selected(subject)
        self.assertEqual(subject.handover_egn_var.get(), "0012345678")
        subject.base_var.set("База Варна")
        ZaraExApp.on_base_changed(subject)
        self.assertEqual(subject.handover_name_var.get(), "")
        self.assertEqual(subject.handover_egn_var.get(), "")
        self.assertEqual(widget["values"], ["Иван Петров"])

    def test_saved_people_survive_restart_and_old_data_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(directory + "/zaraex_data.json", "w", encoding="utf-8") as file:
                json.dump({"products": []}, file)
            with patch("app.__file__", directory + "/app.py"):
                store = DataStore()
                self.assertIn("handover_people", store.data)
                store.data["handover_people"].append(self.person())
                store.save()
                self.assertEqual(DataStore().data["handover_people"], [self.person()])

    def test_base_deletion_removes_assigned_people_after_confirmation(self):
        self.data["handover_people"] = [self.person(), self.person(base="База Варна")]
        tree = Mock()
        tree.selection.return_value = ["0"]
        subject = SimpleNamespace(
            store=SimpleNamespace(data=self.data),
            cancel_record_edit=Mock(),
            save_and_refresh=Mock(),
        )
        with patch("app.messagebox.askyesno", return_value=True):
            ZaraExApp.delete_settings_item(subject, "bases", tree)
        self.assertEqual(self.data["handover_people"], [self.person(base="База Варна")])
        self.assertEqual(self.data["bases"], [{"name": "База Варна"}])


if __name__ == "__main__":
    unittest.main()
