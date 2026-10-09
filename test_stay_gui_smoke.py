"""GUI smoke test for Windows or a Linux session with an X display."""

import json
import os
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "win32" or os.environ.get("DISPLAY"),
                     "Requires a Tk display")
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
                        "ZaraEx – Товарения",
                        "ZaraEx – Настройки",
                        "НАП – Декларации за престой",
                    ])
                    self.assertTrue(app.home_page.winfo_ismapped())
                    self.assertFalse(app.notebook.winfo_ismapped())
                    app.module_buttons["import"].invoke()
                    app.ukn_var.set("00001234")
                    app.handover_name_var.set("Иван Иванов")
                    self.assertEqual(app.notebook.select(), str(app.main_tab))
                    self.assertEqual(app.notebook.tab(app.settings_tab, "state"), "normal")
                    self.assertEqual(app.notebook.tab(app.stay_tab, "state"), "hidden")
                    app.home_button.invoke()
                    app.module_buttons["stay"].invoke()
                    self.assertEqual(app.notebook.select(), str(app.stay_tab))
                    self.assertEqual(app.notebook.tab(app.main_tab, "state"), "hidden")
                    stay.address_entry.delete(0, tk.END)
                    stay.address_entry.insert(0, "ул. Примерна")
                    app.home_button.invoke()
                    app.module_buttons["import"].invoke()
                    self.assertEqual(app.ukn_var.get(), "00001234")
                    self.assertEqual(app.handover_name_var.get(), "Иван Иванов")
                    app.home_button.invoke()
                    app.module_buttons["stay"].invoke()
                    self.assertEqual(stay.address_entry.get(), "ул. Примерна")
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
