"""Linked NRA address fields using the same catalogues as ZaraEx base addresses."""

import json
from pathlib import Path
import sys

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
with (RESOURCE_ROOT / "locations.json").open(encoding="utf-8") as file:
    LOCATIONS = json.load(file)
with (RESOURCE_ROOT / "city_municipalities.json").open(encoding="utf-8") as file:
    CITY_MUNICIPALITIES = json.load(file)

FIELDS = ("region", "municipality", "city")
CATALOGUES = dict(zip(FIELDS, ("domain", "municipality", "city")))


def available_locations(field, region_code="", municipality_code=""):
    items = LOCATIONS[CATALOGUES[field]]
    if field == "municipality":
        return [item for item in items if region_code and item["code"].startswith(region_code)]
    if field == "city":
        return [item for item in items if municipality_code
                and CITY_MUNICIPALITIES.get(item["code"]) == municipality_code]
    return items


def choice_label(item):
    name = "Столична (София)" if item["code"] == "SOF46" else item["name"]
    return f"{name} · {item['code']}"


def resolve_location(items, value, preferred_code=""):
    text = value.strip().casefold()
    matches = [item for item in items if text in (
        item["name"].casefold(), item["code"].casefold(), choice_label(item).casefold(),
        *(('софия', 'столична (софия)', 'столична община') if item["code"] == "SOF46" else ()),
    )]
    if len(matches) == 1:
        return matches[0]
    return next((item for item in matches if item["code"] == preferred_code), None)


def validate_location_codes(region_code, municipality_code, city_code):
    if not any(item["code"] == region_code for item in LOCATIONS["domain"]):
        raise ValueError("Изберете валидна област от предложенията.")
    if not any(item["code"] == municipality_code
               for item in available_locations("municipality", region_code)):
        raise ValueError("Общината не принадлежи на избраната област. Изберете я от предложенията.")
    if not any(item["code"] == city_code
               for item in available_locations("city", region_code, municipality_code)):
        raise ValueError("Населеното място не принадлежи на избраната община. Изберете го от предложенията.")


class LocationSelector:
    """Keep one set of name/code fields consistent, including old saved values."""

    def __init__(self, entries, codes):
        self.entries = entries
        self.codes = codes
        self.updating = False
        self.choices = {}
        for field in FIELDS:
            entries[field].set_on_select(lambda value, field=field: self.select(field, value))
            entries[field].on_change_callback = lambda field=field: self.changed(field)
            entries[field].bind("<FocusOut>", lambda event, field=field: self.commit(field), add="+")
        self.restore()

    def refresh_choices(self):
        for field in FIELDS:
            self.choices[field] = available_locations(
                field, self.codes["region"].get(), self.codes["municipality"].get())
            self.entries[field].autocomplete_list = sorted(
                [choice_label(item) for item in self.choices[field]], key=str.casefold)

    def assign(self, field, item):
        entry = self.entries[field]
        entry.var.set(item["name"] if item else "")
        self.codes[field].set(item["code"] if item else "")
        entry.configure(fg="#172D49")
        entry.hide_listbox()

    def changed(self, field):
        if self.updating:
            return
        self.updating = True
        try:
            self.refresh_choices()
            item = resolve_location(self.choices[field], self.entries[field].get(), self.codes[field].get())
            self.codes[field].set(item["code"] if item else "")
            self.sync_children(field)
        finally:
            self.updating = False

    def sync_children(self, field):
        if field == "region":
            self.refresh_choices()
            item = resolve_location(self.choices["municipality"],
                                    self.entries["municipality"].get(), self.codes["municipality"].get())
            if item is None and len(self.choices["municipality"]) == 1:
                item = self.choices["municipality"][0]
            self.assign("municipality", item)
        if field in ("region", "municipality"):
            self.refresh_choices()
            item = resolve_location(self.choices["city"], self.entries["city"].get(), self.codes["city"].get())
            self.assign("city", item)
        self.refresh_choices()

    def select(self, field, value):
        self.updating = True
        try:
            self.refresh_choices()
            item = resolve_location(self.choices[field], value, self.codes[field].get())
            self.assign(field, item)
            self.sync_children(field)
        finally:
            self.updating = False

    def commit(self, field):
        self.select(field, self.entries[field].get())

    def restore(self):
        self.updating = True
        try:
            for field in FIELDS:
                self.refresh_choices()
                item = resolve_location(self.choices[field], self.entries[field].get(), self.codes[field].get())
                if field == "municipality" and item is None and len(self.choices[field]) == 1:
                    item = self.choices[field][0]
                self.assign(field, item)
            self.refresh_choices()
        finally:
            self.updating = False
