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




class IssuerEikExportTests(unittest.TestCase):
    def test_issuer_eik_uses_identifier_and_never_exceeds_14_characters(self):
        from unittest.mock import Mock, patch
        from app import ZaraExApp

        address = {
            "region": "Русе", "region_code": "RSE",
            "municipality": "Бяла (Русе)", "municipality_code": "RSE04",
            "city": "гр.Бяла (Русе)", "city_code": "07603",
        }
        record = {
            "ukn": "00001", "add_no": "00002",
            "date": datetime(2026, 10, 8), "fuel_kind": "diesel",
            "kn_code": "27102011", "product_name": "Diesel", "quantity": 100.0,
            "base_name": "Дълго наименование на петролна база",
            "base_eik": "", "base_address": address,
            "company_name": "Transport", "company_eik": "000012345",
            "vehicle": "Truck", "driver_name": "Driver", "driver_egn": "0012345678",
            "zara_code": "03",
        }
        examples = (
            ("000012345", "000012345"),
            ("001234567890123456", "00123456789012"),
            (" 000012345 ", "000012345"),
        )
        for source, expected in examples:
            with self.subTest(base_eik=source):
                record["base_eik"] = source
                workbook = Mock()
                subject = SimpleNamespace(
                    records=[record], write_text=ZaraExApp.write_text
                )
                with (
                    patch("app.ExcelWorkbook", return_value=workbook),
                    patch("app.validate_address", return_value=address),
                    patch("app.filedialog.asksaveasfilename", return_value="generated.xls"),
                    patch("app.messagebox.showinfo") as showinfo,
                    patch("app.messagebox.showerror") as showerror,
                ):
                    ZaraExApp.export_xls(subject)

                showerror.assert_not_called()
                showinfo.assert_called_once()
                sheet = workbook.sheet.return_value
                sheet.write.assert_any_call(1, 44, expected, "@")  # AS
                sheet.write.assert_any_call(1, 7, record["base_name"], "@")  # H
                self.assertLessEqual(len(expected), 14)

if __name__ == "__main__":
    unittest.main()
