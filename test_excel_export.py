import unittest
from types import SimpleNamespace

from excel_export import ExcelSheet


class HeaderCheckTests(unittest.TestCase):
    def test_labels_empty_cells_and_preserves_existing_values(self):
        cells = {}

        def get_cell(row, column):
            return cells.setdefault((row, column), SimpleNamespace(Value=None, NumberFormat=""))

        sheet = ExcelSheet(SimpleNamespace(Cells=get_cell))
        headers = ["УКН", "Адрес", "Количество", "Плащане", "", "Документ"]
        sheet.write(1, 0, "000123", "@")
        sheet.write(1, 2, 125.5, "0.00")
        sheet.write(1, 3, 0, "0")
        sheet.write(1, 5, "", "@")
        sheet.fill_empty_with_headers(1, headers)
        self.assertEqual(get_cell(2, 1).Value, "000123")
        self.assertEqual(get_cell(2, 2).Value, "Адрес")
        self.assertEqual(get_cell(2, 3).Value, 125.5)
        self.assertEqual(get_cell(2, 4).Value, 0)
        self.assertIsNone(get_cell(2, 5).Value)
        self.assertEqual(get_cell(2, 6).Value, "Документ")
        self.assertEqual(get_cell(2, 2).NumberFormat, "@")
        self.assertIsNone(get_cell(1, 2).Value)


if __name__ == "__main__":
    unittest.main()
