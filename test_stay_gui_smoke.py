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
    def test_sofia_selection_filters_children_and_populates_codes(self):
        from app import ZaraExApp
        from nap_stay import eStayGen as stay

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"LOCALAPPDATA": directory}):
            app = ZaraExApp()
            try:
                app.open_workspace("stay")
                app.update()
                stay.region_entry.insert(0, "София")
                app.update()
                popup = stay.region_entry.listbox
                suggestions = popup.get(0, tk.END)
                index = next(i for i, text in enumerate(suggestions) if text.endswith(" · SFO"))
                self.assertGreater(index, 0)  # Reproduce clicking a non-first suggestion.
                box = popup.bbox(index)
                popup.event_generate("<Button-1>", x=8, y=box[1] + box[3] // 2)
                self.assertEqual(stay.region_code_var.get(), "SFO")
                stay.region_entry.var.set("София")
                app.update()
                popup = stay.region_entry.listbox
                suggestions = popup.get(0, tk.END)
                index = next(i for i, text in enumerate(suggestions) if "София (столица)" in text)
                box = popup.bbox(index)
                popup.event_generate("<Button-1>", x=8, y=box[1] + box[3] // 2)
                self.assertEqual(stay.region_code_var.get(), "SOF")
                self.assertEqual(stay.municipality_entry.get(), "Столична")
                self.assertEqual(stay.municipality_code_var.get(), "SOF46")
                stay.municipality_entry.delete(0, tk.END)
                stay.municipality_entry.insert(0, "София")
                stay.municipality_entry.event_generate("<FocusOut>")
                self.assertEqual(stay.municipality_entry.get(), "Столична")
                self.assertEqual(stay.municipality_code_var.get(), "SOF46")
                stay.city_entry.insert(0, "София")
                stay.city_entry.selection(None)
                self.assertEqual(stay.city_code_var.get(), "68134")
                row = app.stay_tab.stay_content.saved_address_rows[0]
                row["region"].var.set("София (столица)")
                row["city"].var.set("гр.София")
                self.assertEqual(row["municipality_code_var"].get(), "SOF46")
                self.assertEqual(row["city_code_var"].get(), "68134")
                stay.region_entry.var.set("Варна")
                self.assertEqual(stay.region_code_var.get(), "VAR")
                self.assertEqual(stay.municipality_code_var.get(), "")
                self.assertEqual(stay.city_code_var.get(), "")
                self.assertTrue(stay.municipality_entry.autocomplete_list)
                self.assertTrue(all("VAR" in value for value in stay.municipality_entry.autocomplete_list))
                self.assertEqual(row["municipality_code_var"].get(), "SOF46")
                stay.region_entry.var.set("невалидна област")
                self.assertEqual(stay.region_code_var.get(), "")
                self.assertEqual(stay.municipality_entry.autocomplete_list, [])
            finally:
                app.close_application()

    def test_saved_address_card_can_edit_apply_and_delete(self):
        from app import ZaraExApp
        from nap_stay import eStayGen as stay

        saved = {
            "company": "Тест транспорт", "region_code": "SOF",
            "municipality_code": "SOF46", "city_code": "68134",
            "address": "ул. Примерна", "number": "12",
        }
        for key, catalogue in (("region", stay.DOMAIN_DICT),
                               ("municipality", stay.MUNICIPALITY_DICT),
                               ("city", stay.CITY_DICT)):
            saved[key] = next(name for name, code in catalogue.items()
                              if code == saved[key + "_code"])
        # A legacy template may call the municipality Sofia and omit its code.
        saved["municipality"] = "София"
        saved["municipality_code"] = ""
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                path = stay.saved_addresses_path()
                with open(path, "w", encoding="utf-8") as file:
                    json.dump([saved, {}, {}, {}, {}], file)
                app = ZaraExApp()
                try:
                    app.open_workspace("stay")
                    app.update()
                    row = app.stay_tab.stay_content.saved_address_rows[0]
                    self.assertEqual(row["municipality"].get(), "Столична")
                    self.assertEqual(row["municipality_code_var"].get(), "SOF46")
                    self.assertFalse(row["address"].winfo_ismapped())
                    row["toggle_button"].invoke()
                    app.update()
                    self.assertTrue(row["address"].winfo_ismapped())
                    row["address"].delete(0, tk.END)
                    row["address"].insert(0, "ул. Нов адрес")
                    row["address"].event_generate("<FocusOut>")
                    with open(path, encoding="utf-8") as file:
                        self.assertEqual(json.load(file)[0]["address"], "ул. Нов адрес")
                    actions = row["toggle_button"].master.winfo_children()
                    next(w for w in actions if w.cget("text") == "Приложи адрес").invoke()
                    self.assertEqual(stay.address_entry.get(), "ул. Нов адрес")
                    self.assertEqual(stay.number_entry.get(), "12")
                    self.assertEqual(stay.city_code_var.get(), "68134")
                    next(w for w in actions if w.cget("text") == "Изтрий адрес").invoke()
                    with open(path, encoding="utf-8") as file:
                        self.assertEqual(json.load(file)[0], {})
                    self.assertEqual(stay.address_entry.get(), "ул. Нов адрес")
                finally:
                    app.close_application()

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
