import unittest
from unittest.mock import Mock

from delivery_objects import DELIVERY_OBJECTS, resolve_delivery_object, write_delivery_object
from settings_editor import prepare_settings_edit
import test_editing
from app import ZaraExApp


class DeliveryObjectTests(unittest.TestCase):
    def test_export_name_and_code_with_leading_zeros(self):
        for name, code in DELIVERY_OBJECTS.items():
            sheet = Mock()
            write_delivery_object(sheet, 1, name)
            sheet.write.assert_any_call(1, 28, name, "@")
            sheet.write.assert_any_call(1, 29, code, "@")
            self.assertEqual(sheet.write.call_count, 2)

    def test_missing_selection_rejected(self):
        with self.assertRaises(ValueError):
            resolve_delivery_object("")

    def test_base_edit_updates_code_from_selected_object(self):
        fixture = test_editing.EditingTests()
        fixture.setUp()
        updated = prepare_settings_edit(fixture.data, "bases", 0, {"delivery_object": "ПСБ ПЛОВДИВ"})
        self.assertEqual(updated["delivery_object_code"], "0005")

    def test_record_keeps_selected_base_object(self):
        fixture = test_editing.EditingTests()
        fixture.setUp()
        subject = fixture.record_subject()
        ZaraExApp.add_record(subject)
        self.assertEqual(subject.records[0]["delivery_object"], "ПСБ РУСЕ")
        self.assertEqual(subject.records[0]["delivery_object_code"], "0026")


if __name__ == "__main__":
    unittest.main()
