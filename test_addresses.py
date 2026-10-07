import unittest
from unittest.mock import Mock, patch

from addresses import LOCATIONS, validate_address, write_base_address, format_address
from settings_editor import prepare_settings_edit
from app import ZaraExApp, DataStore
import test_editing


class AddressTests(unittest.TestCase):
    def setUp(self):
        self.address = {"region": "Русе", "region_code": "RSE", "municipality": "Бяла (Русе)", "municipality_code": "RSE04", "city": "гр.Бяла (Русе)", "city_code": "07603", "street": "Петролна база", "number": "12"}

    def test_exact_source_codes_and_duplicate_city_names(self):
        self.assertIn({"name": "гр.Бяла (Русе)", "code": "07603"}, LOCATIONS["city"])
        self.assertIn({"name": "гр.Бяла (Варна)", "code": "07598"}, LOCATIONS["city"])
        same_name = [item for item in LOCATIONS["city"] if item["name"] == "с.Бяла река"]
        self.assertGreater(len(same_name), 1)
        self.assertEqual(len({item["code"] for item in same_name}), len(same_name))

    def test_mismatched_region_municipality_rejected(self):
        with self.assertRaises(ValueError):
            validate_address(dict(self.address, region="Варна", region_code="VAR"))

    def test_city_name_and_code_must_match(self):
        with self.assertRaises(ValueError):
            validate_address(dict(self.address, city_code="07598"))

    def test_address_and_codes_exported_to_receiving_columns_as_text(self):
        sheet = Mock()
        write_base_address(sheet, 1, self.address)
        sheet.write.assert_any_call(1, 35, "07603", "@")
        sheet.write.assert_any_call(1, 31, "RSE", "@")
        sheet.write.assert_any_call(1, 33, "RSE04", "@")
        sheet.write.assert_any_call(1, 38, "Петролна база 12", "@")
        self.assertEqual(sheet.write.call_count, 7)

    def test_number_optional_and_street_required(self):
        self.assertEqual(validate_address(dict(self.address, number=""))["number"], "")
        with self.assertRaises(ValueError):
            validate_address(dict(self.address, street=""))

    def test_base_edit_includes_validated_address(self):
        data = {"bases": [{"name": "Base", "eik": "001"}]}
        updated = prepare_settings_edit(data, "bases", 0, {"address": self.address})
        self.assertEqual(updated["address"]["city_code"], "07603")
        self.assertIn("Петролна база 12", format_address(updated["address"]))

    def record_subject(self):
        fixture = test_editing.EditingTests()
        fixture.setUp()
        return fixture.record_subject()

    def test_record_contains_independent_address_snapshot(self):
        subject = self.record_subject()
        ZaraExApp.add_record(subject)
        subject.store.data["bases"][0]["address"]["city_code"] = "changed"
        self.assertEqual(subject.records[0]["base_address"]["city_code"], "07603")

    def test_export_delivery_address_and_name_from_selected_base(self):
        subject = self.record_subject()
        subject.store.data["bases"][0]["name"] = "Петрол АД"
        subject.store.data["bases"][0]["address"]["street"] = "ул. Васил Априлов"
        subject.store.data["bases"][0]["address"]["number"] = "43"
        ZaraExApp.add_record(subject)
        subject.write_text = ZaraExApp.write_text
        workbook = Mock()
        sheet = workbook.sheet.return_value
        with patch("app.ExcelWorkbook", return_value=workbook), patch("app.filedialog.asksaveasfilename", return_value="test.xls"), patch("app.messagebox.showinfo"), patch("app.messagebox.showerror") as error:
            ZaraExApp.export_xls(subject)
        error.assert_not_called()
        sheet.write.assert_any_call(1, 17, "ул. Васил Априлов 43", "@")
        sheet.write.assert_any_call(1, 18, "Петрол АД", "@")
        workbook.save.assert_called_once_with("test.xls")

    def test_legacy_base_without_address_requires_completion(self):
        subject = self.record_subject()
        subject.store.data["bases"][0].pop("address")
        with patch("app.messagebox.showerror") as error:
            ZaraExApp.add_record(subject)
        error.assert_called_once()
        self.assertEqual(subject.records, [{"ukn": "old"}])


if __name__ == "__main__":
    unittest.main()
