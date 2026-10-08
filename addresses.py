"""Address selection with the exact location codes from E_STAY_GEN."""

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk


def load_locations():
    with Path(__file__).with_name("locations.json").open(encoding="utf-8") as file:
        return json.load(file)


LOCATIONS = load_locations()
with Path(__file__).with_name("city_municipalities.json").open(encoding="utf-8") as file:
    CITY_MUNICIPALITIES = json.load(file)

LOCATION_FIELDS = (("region", "domain", "Област"), ("municipality", "municipality", "Община"), ("city", "city", "Населено място"))


def validate_address(address):
    result = dict(address)
    for field, catalog, label in LOCATION_FIELDS:
        name, code = result.get(field, ""), result.get(field + "_code", "")
        if not any(item["name"] == name and item["code"] == code for item in LOCATIONS[catalog]):
            raise ValueError(f"Избери валидно поле „{label}“ от списъка.")
    if not result["municipality_code"].startswith(result["region_code"]):
        raise ValueError("Общината не е към избраната област.")
    mapped_municipality = CITY_MUNICIPALITIES.get(result["city_code"])
    if mapped_municipality and mapped_municipality != result["municipality_code"]:
        raise ValueError("Населеното място не принадлежи на избраната община.")
    if not mapped_municipality:
        raise ValueError("Липсва потвърдена община за това населено място. Не може да се експортира с непроверен адрес.")
    result["street"] = result.get("street", "").strip()
    result["number"] = result.get("number", "").strip()
    if not result["street"]:
        raise ValueError("Въведи адрес на петролната база.")
    return result


def format_address(address):
    if not address:
        return ""
    street = " ".join(filter(None, (address.get("street", ""), address.get("number", ""))))
    return ", ".join(filter(None, (address.get("city", ""), street)))


def write_base_address(sheet, row, address):
    """AE–AM describe where the fuel is received from the selected base."""
    address = validate_address(address)
    for column, key in ((30, "region"), (31, "region_code"), (32, "municipality"), (33, "municipality_code"), (34, "city"), (35, "city_code")):
        sheet.write(row, column, address[key], "@")
    street = " ".join(filter(None, (address["street"], address["number"])))
    sheet.write(row, 38, street, "@")


class AddressFields(ttk.LabelFrame):
    def __init__(self, parent, address=None):
        super().__init__(parent, text="Адрес на петролната база", padding=10)
        address = address or {}
        self.variables = {}
        self.codes = {}
        self.combos = {}
        self.choices = {}
        for row, (field, catalog, label) in enumerate(LOCATION_FIELDS):
            choices = {f"{item['name']} · {item['code']}": item for item in LOCATIONS[catalog]}
            self.choices[field] = choices
            display = next((text for text, item in choices.items() if item["name"] == address.get(field) and item["code"] == address.get(field + "_code")), "")
            var = tk.StringVar(self, value=display)
            code = tk.StringVar(self, value=address.get(field + "_code", ""))
            self.variables[field] = var
            self.codes[field] = code
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            combo = ttk.Combobox(self, textvariable=var, values=list(choices), width=42)
            combo.grid(row=row, column=1, sticky="ew", pady=4)
            self.combos[field] = combo
            ttk.Entry(self, textvariable=code, state="readonly", width=9).grid(row=row, column=2, padx=(8, 0), pady=4)
            combo.bind("<KeyRelease>", lambda event, key=field: self.filter_choices(key))
            combo.bind("<<ComboboxSelected>>", lambda event, key=field: self.selected(key))
            combo.bind("<FocusOut>", lambda event, key=field: self.selected(key))
        for row, (key, label) in enumerate((("street", "Улица / местност"), ("number", "Номер")), start=3):
            var = tk.StringVar(self, value=address.get(key, ""))
            self.variables[key] = var
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            ttk.Entry(self, textvariable=var, width=42).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(self, text="Пиши име или код и избери от списъка. Кодът се попълва автоматично.").grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.columnconfigure(1, weight=1)
        self.refresh_municipalities()
        self.refresh_cities()

    def available_choices(self, field):
        choices = self.choices[field]
        if field == "municipality" and self.codes["region"].get():
            return {text: item for text, item in choices.items() if item["code"].startswith(self.codes["region"].get())}
        if field == "city" and self.codes["municipality"].get():
            municipality_code = self.codes["municipality"].get()
            return {text: item for text, item in choices.items() if CITY_MUNICIPALITIES.get(item["code"]) == municipality_code}
        if field == "city":
            return {}
        return choices

    def filter_choices(self, field):
        text = self.variables[field].get().casefold()
        self.combos[field]["values"] = [label for label in self.available_choices(field) if text in label.casefold()]
        item = self.available_choices(field).get(self.variables[field].get())
        self.codes[field].set(item["code"] if item else "")
        if field == "region":
            self.refresh_municipalities()
            self.refresh_cities()
        elif field == "municipality":
            self.refresh_cities()

    def selected(self, field):
        text = self.variables[field].get().strip()
        choices = self.available_choices(field)
        item = choices.get(text)
        if item is None:
            matches = [(label, entry) for label, entry in choices.items() if text.casefold() in entry["name"].casefold() or text.casefold() in entry["code"].casefold()]
            if len(matches) == 1:
                text, item = matches[0]
                self.variables[field].set(text)
        self.codes[field].set(item["code"] if item else "")
        self.combos[field]["values"] = list(choices)
        if field == "region":
            self.refresh_municipalities()
            self.refresh_cities()
        elif field == "municipality":
            self.refresh_cities()

    def refresh_municipalities(self):
        choices = self.available_choices("municipality")
        self.combos["municipality"]["values"] = list(choices)
        current = self.variables["municipality"].get()
        if current and current not in choices:
            self.variables["municipality"].set("")
            self.codes["municipality"].set("")

    def refresh_cities(self):
        choices = self.available_choices("city")
        self.combos["city"]["values"] = list(choices)
        current = self.variables["city"].get()
        if current and current not in choices:
            self.variables["city"].set("")
            self.codes["city"].set("")

    def get_address(self):
        address = {key: self.variables[key].get().strip() for key in ("street", "number")}
        for field, _, _ in LOCATION_FIELDS:
            self.selected(field)
            item = self.available_choices(field).get(self.variables[field].get())
            address[field] = item["name"] if item else ""
            address[field + "_code"] = item["code"] if item else ""
        return validate_address(address)

    def clear(self):
        for var in self.variables.values():
            var.set("")
        for var in self.codes.values():
            var.set("")
        for field in self.combos:
            self.combos[field]["values"] = list(self.available_choices(field))
