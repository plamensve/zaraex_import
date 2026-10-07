"""ZaraEx loading-base objects from the supplied correctly populated file."""

DELIVERY_OBJECTS = {
    "АНЕ ЛУКОЙЛ Нефтохим Бургас": "0001",
    "ПСБ РУСЕ": "0026",
    "ПСБ ПЛОВДИВ": "0005",
    "ПСБ АСПАРУХОВО": "0008",
}


def resolve_delivery_object(name):
    if name not in DELIVERY_OBJECTS:
        raise ValueError("Избери „Обект дост. ZaraEx“ от списъка.")
    return name, DELIVERY_OBJECTS[name]


def write_delivery_object(sheet, row, name):
    name, code = resolve_delivery_object(name)
    # Confirmed by the original EAdd file: AC is the receiving place,
    # AD is its code; leading zeros must be retained.
    sheet.write(row, 28, name, "@")
    sheet.write(row, 29, code, "@")
