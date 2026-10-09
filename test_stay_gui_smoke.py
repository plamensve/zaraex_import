"""GUI smoke test for Windows CI; headless Linux tests cover XML separately."""

import json
import os
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "win32", "Requires Windows Tkinter")
class EmbeddedStayGuiSmokeTests(unittest.TestCase):
    def test_tabs_and_original_estay_controls_open_in_single_window(self):
        from app import ZaraExApp
        from nap_stay import eStayGen as stay

        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                app = ZaraExApp()
                try:
                    app.update_idletasks()
                    labels = [app.notebook.tab(item, "text") for item in app.notebook.tabs()]
                    self.assertEqual(labels, [
                        "ЗараЕкс – Товарения",
                        "ЗараЕкс – Настройки",
                        "НАП – Декларации за престой",
                    ])
                    self.assertIs(tk._default_root, app)
                    self.assertTrue(stay.DOMAIN_DICT)
                    self.assertTrue(stay.CITY_DICT)
                    self.assertEqual(stay.date_entry.cget("date_pattern").lower(), "dd.mm.yyyy")
                    self.assertTrue(stay.region_entry.winfo_exists())
                    self.assertTrue(stay.municipality_entry.winfo_exists())
                    self.assertTrue(stay.city_entry.winfo_exists())

                    def descendants(widget):
                        for child in widget.winfo_children():
                            yield child
                            yield from descendants(child)

                    buttons = [
                        widget.cget("text")
                        for widget in descendants(app.stay_tab)
                        if isinstance(widget, tk.Button)
                    ]
                    self.assertEqual(buttons.count("Приложи адрес"), 5)
                    self.assertEqual(buttons.count("Изтрий адрес"), 5)
                    self.assertIn("Генерирай XML", buttons)
                finally:
                    app.close_application()

                path = os.path.join(directory, "ZaraExImport", "nap_stay", "saved_addresses.json")
                self.assertTrue(os.path.exists(path))
                with open(path, encoding="utf-8") as file:
                    self.assertEqual(len(json.load(file)), 5)


if __name__ == "__main__":
    unittest.main()
