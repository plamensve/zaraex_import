"""Initial product nomenclature and one-time upgrade of local settings."""

import json
from pathlib import Path


CATALOG_VERSION = 1
LEGACY_NAMES = {
    "ГОРИВО ЗА ДИЗЕЛОВИ ДВИГАТЕЛИ с мин. 6% обемни БД, вкл. 2 % об. БД от ново пок.": "011",
    "Гориво за извън пътна техника и трактори": "012",
}


def load_catalog():
    with Path(__file__).with_name("products.json").open(encoding="utf-8") as file:
        return json.load(file)


def migrate_catalog(data):
    if data.get("product_catalog_version", 0) >= CATALOG_VERSION:
        return False
    products = data.setdefault("products", [])
    for source in load_catalog():
        existing = next((p for p in products if
            p.get("catalog_code") == source["catalog_code"]
            or p.get("name", "").strip() == source["name"]
            or (source["link_code"] and p.get("link_code") == source["link_code"])
            or (not p.get("link_code")
                and LEGACY_NAMES.get(p.get("name")) == source["catalog_code"])
        ), None)
        if existing is None:
            products.append(dict(source))
        else:
            existing.setdefault("catalog_code", source["catalog_code"])
            for key in ("link_code", "kn_code", "fuel_kind", "helper_bj"):
                if existing.get(key) in (None, ""):
                    existing[key] = source[key]
            if existing.get("name") in LEGACY_NAMES:
                existing["name"] = source["name"]
    data["product_catalog_version"] = CATALOG_VERSION
    return True
