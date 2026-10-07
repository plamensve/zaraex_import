import unittest
from datetime import date, datetime, timezone, timedelta
from types import SimpleNamespace

from excel_export import ExcelSheet


class ExcelDateTests(unittest.TestCase):
    def test_calendar_dates_are_written_as_numbers_without_com_datetime(self):
        for value in (datetime(2026, 10, 7), date(2026, 10, 7), datetime(2026, 10, 7, tzinfo=timezone(timedelta(hours=3)))):
            cell = SimpleNamespace(Value=None, Value2=None, NumberFormat="")
            sheet = ExcelSheet(SimpleNamespace(Cells=lambda row, column: cell))
            sheet.write(1, 2, value, "DD.MM.YYYY")
            self.assertEqual(cell.Value2, 46302)
            self.assertIsNone(cell.Value)
            self.assertEqual(cell.NumberFormat, "DD.MM.YYYY")

    def test_leap_day_and_year_boundary_round_trip(self):
        for value in (date(2024, 2, 29), date(2026, 12, 31), date(2027, 1, 1)):
            cell = SimpleNamespace(Value=None, Value2=None, NumberFormat="")
            sheet = ExcelSheet(SimpleNamespace(Cells=lambda row, column: cell))
            sheet.write(1, 47, value, "DD.MM.YYYY")
            self.assertEqual(date(1899, 12, 30) + timedelta(days=cell.Value2), value)

    def test_1904_workbook_calendar_is_supported(self):
        cell = SimpleNamespace(Value=None, Value2=None, NumberFormat="")
        sheet = ExcelSheet(SimpleNamespace(Cells=lambda row, column: cell), date1904=True)
        sheet.write(1, 2, date(2026, 10, 7), "DD.MM.YYYY")
        self.assertEqual(date(1904, 1, 1) + timedelta(days=cell.Value2), date(2026, 10, 7))

    def test_identifiers_keep_leading_zeros(self):
        cell = SimpleNamespace(Value=None, Value2=None, NumberFormat="")
        sheet = ExcelSheet(SimpleNamespace(Cells=lambda row, column: cell))
        sheet.write(1, 29, "0026", "@")
        self.assertEqual(cell.Value, "0026")
        self.assertIsNone(cell.Value2)


if __name__ == "__main__":
    unittest.main()
