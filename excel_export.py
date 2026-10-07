"""Write true Excel 97–2003 files using the original ZaraEx template."""

from pathlib import Path
from datetime import date, datetime


class ExcelSheet:
    def __init__(self, sheet, date1904=False):
        self.sheet = sheet
        self.date1904 = date1904

    def write(self, row, column, value, number_format):
        cell = self.sheet.Cells(row + 1, column + 1)
        cell.NumberFormat = number_format
        if isinstance(value, date):
            calendar_date = value.date() if isinstance(value, datetime) else value
            epoch = date(1904, 1, 1) if self.date1904 else date(1899, 12, 30)
            cell.Value2 = (calendar_date - epoch).days
        else:
            cell.Value = value


class ExcelWorkbook:
    def __init__(self):
        self.excel = None
        self.workbook = None
        template = Path(__file__).with_name("zaraex_template.xls")
        if not template.is_file():
            raise FileNotFoundError("Липсва zaraex_template.xls до приложението.")
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError(
                "Експортът изисква Windows, Microsoft Excel и pywin32. "
                "Изпълни: python -m pip install -r requirements.txt"
            ) from exc
        try:
            self.excel = win32com.client.DispatchEx("Excel.Application")
            self.excel.Visible = False
            self.excel.DisplayAlerts = False
            self.workbook = self.excel.Workbooks.Open(
                str(template.resolve()), UpdateLinks=0, ReadOnly=True
            )
            for name in ("EAdd", "EPad"):
                sheet = self.workbook.Worksheets(name)
                last_row = sheet.UsedRange.Row + sheet.UsedRange.Rows.Count - 1
                if last_row >= 2:
                    sheet.Range(sheet.Cells(2, 1), sheet.Cells(last_row, 63)).ClearContents()
        except Exception:
            self.close()
            raise

    def sheet(self, name):
        return ExcelSheet(self.workbook.Worksheets(name), date1904=bool(self.workbook.Date1904))

    def save(self, output):
        output = Path(output).resolve()
        if output == Path(__file__).with_name("zaraex_template.xls").resolve():
            raise ValueError("Избери друго име: вътрешният шаблон не може да се презаписва.")
        self.workbook.SaveAs(str(output), FileFormat=56)

    def close(self):
        try:
            if self.workbook is not None:
                self.workbook.Close(SaveChanges=False)
        finally:
            self.workbook = None
            if self.excel is not None:
                try:
                    self.excel.Quit()
                finally:
                    self.excel = None
