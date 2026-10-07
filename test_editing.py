import copy
import json
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import ZaraExApp, DataStore
from settings_editor import SettingsEditorMixin, prepare_settings_edit, apply_settings_edit


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "products": [{"name": "Diesel", "link_code": "31", "kn_code": "27102011", "helper_bj": 31, "catalog_code": "011"}],
            "transport_companies": [{"name": "Transport", "eik": "00123"}],
            "vehicles": [{"registration": "Truck", "company_eik": "00123"}],
            "drivers": [{"name": "Driver", "egn": "0012345678", "company_eik": "00123"}],
            "bases": [{"name": "Base", "eik": "00987", "address": {"region": "Русе", "region_code": "RSE", "municipality": "Бяла (Русе)", "municipality_code": "RSE04", "city": "гр.Бяла (Русе)", "city_code": "07603", "street": "Петролна база", "number": "12"}}],
        }

    def test_company_eik_edit_retains_relationships(self):
        edited = prepare_settings_edit(self.data, "transport_companies", 0, {"eik": "00456"})
        apply_settings_edit(self.data, "transport_companies", 0, edited)
        self.assertEqual(self.data["vehicles"][0]["company_eik"], "00456")
        self.assertEqual(self.data["drivers"][0]["company_eik"], "00456")
        self.assertEqual(self.data["drivers"][0]["egn"], "0012345678")

    def test_duplicate_link_rejected_without_mutation(self):
        self.data["products"].append({"name": "Other", "link_code": "42"})
        original = copy.deepcopy(self.data)
        with self.assertRaises(ValueError):
            prepare_settings_edit(self.data, "products", 0, {"link_code": "42"})
        self.assertEqual(self.data, original)

    def test_blank_source_codes_and_metadata_preserved(self):
        edited = prepare_settings_edit(self.data, "products", 0, {"link_code": "", "helper_bj": ""})
        self.assertEqual(edited["catalog_code"], "011")
        self.assertEqual(edited["link_code"], "")
        self.assertIsNone(edited["helper_bj"])

    def test_unknown_company_rejected(self):
        with self.assertRaises(ValueError):
            prepare_settings_edit(self.data, "vehicles", 0, {"company_eik": "unknown"})

    def test_deleted_catalog_product_stays_deleted_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.__file__", directory + "/app.py"):
                store = DataStore()
                deleted_code = store.data["products"].pop(0)["catalog_code"]
                store.save()
                reloaded = DataStore()
                self.assertFalse(any(p.get("catalog_code") == deleted_code for p in reloaded.data["products"]))

    def test_existing_settings_still_receive_catalog_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(directory + "/zaraex_data.json", "w") as file:
                json.dump({"products": []}, file)
            with patch("app.__file__", directory + "/app.py"):
                self.assertEqual(len(DataStore().data["products"]), 14)

    def record_subject(self):
        subject = SimpleNamespace(store=SimpleNamespace(data=self.data), records=[{"ukn": "old"}], editing_record_index=0)
        values = dict(date="07.10.2026", ukn="00001", add="00002", quantity="100,5", zara="03", product="Diesel", company="Transport", vehicle="Truck", driver="Driver", base="Base")
        for key, value in values.items():
            setattr(subject, key + "_var", Variable(value))
        subject.get_product_by_name = lambda name: self.data["products"][0]
        subject.get_company_by_name = lambda name: self.data["transport_companies"][0]
        subject.get_base_by_name = lambda name: self.data["bases"][0]
        subject.get_driver_by_name_and_company = lambda name, eik: self.data["drivers"][0]
        subject.finish_record_edit = Mock()
        subject.refresh_records_table = Mock()
        return subject

    def test_save_edit_replaces_record_and_preserves_text_identifiers(self):
        subject = self.record_subject()
        ZaraExApp.add_record(subject)
        self.assertEqual(len(subject.records), 1)
        self.assertEqual(subject.records[0]["quantity"], 100.5)
        self.assertEqual(subject.records[0]["ukn"], "00001")
        self.assertEqual(subject.records[0]["driver_egn"], "0012345678")
        self.assertEqual(subject.records[0]["date"], datetime(2026, 10, 7))
        subject.finish_record_edit.assert_called_once()

    def test_invalid_edit_does_not_replace_record(self):
        subject = self.record_subject()
        subject.quantity_var.set("nan")
        with patch("app.messagebox.showerror"):
            ZaraExApp.add_record(subject)
        self.assertEqual(subject.records, [{"ukn": "old"}])
        subject.finish_record_edit.assert_not_called()

    def test_delete_cancel_preserves_records_and_edit_state(self):
        subject = self.record_subject()
        subject.records_tree = Mock()
        subject.records_tree.selection.return_value = ("row",)
        subject.records_tree.item.return_value = (1,)
        subject.cancel_record_edit = Mock()
        with patch("app.messagebox.askyesno", return_value=False):
            ZaraExApp.delete_selected_records(subject)
        self.assertEqual(len(subject.records), 1)
        subject.cancel_record_edit.assert_not_called()
        with patch("app.messagebox.askyesno", return_value=True):
            ZaraExApp.delete_selected_records(subject)
        self.assertEqual(subject.records, [])
        subject.cancel_record_edit.assert_called_once()

    def test_cancel_edit_restores_form_without_changing_record(self):
        subject = self.record_subject()
        subject.record_form_before_edit = {key: "previous" for key in SettingsEditorMixin.record_form_variables(subject)}
        subject.record_form_variables = lambda: SettingsEditorMixin.record_form_variables(subject)
        subject.refresh_company_dependent_dropdowns = Mock()
        subject.update_selection_info = Mock()
        SettingsEditorMixin.cancel_record_edit(subject)
        self.assertEqual(subject.ukn_var.get(), "previous")
        self.assertEqual(subject.records, [{"ukn": "old"}])
        subject.finish_record_edit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
