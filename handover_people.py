"""Helpers for persistent fuel handover personnel and base-scoped suggestions."""


def handover_full_name(person):
    return " ".join(
        str(person.get(key, "")).strip()
        for key in ("first_name", "middle_name", "last_name")
        if str(person.get(key, "")).strip()
    )


def matching_handover_people(people, base_name, query=""):
    """Return only people assigned to this base, optionally filtered by name."""
    needle = query.strip().casefold()
    matches = [
        person for person in people
        if person.get("base_name") == base_name
        and needle in handover_full_name(person).casefold()
    ]
    return sorted(matches, key=lambda person: handover_full_name(person).casefold())


def validate_handover_person(data, person, ignore_index=None):
    """Normalize and validate an entry on add/edit without changing saved data."""
    result = {
        key: str(person.get(key) or "").strip()
        for key in ("first_name", "middle_name", "last_name", "egn", "base_name")
    }
    if not result["first_name"] or not result["last_name"] or not result["egn"] or not result["base_name"]:
        raise ValueError("Име, фамилия, ЕГН и петролна база са задължителни.")
    egn = result["egn"]
    if len(egn) != 10 or not egn.isascii() or not egn.isdigit():
        raise ValueError("ЕГН трябва да съдържа точно 10 цифри.")
    if not any(base.get("name") == result["base_name"] for base in data["bases"]):
        raise ValueError("Избери съществуваща петролна база.")
    full_name = handover_full_name(result).casefold()
    for index, existing in enumerate(data.get("handover_people", [])):
        if index == ignore_index or existing.get("base_name") != result["base_name"]:
            continue
        if existing.get("egn") == egn:
            raise ValueError("В тази петролна база вече има лице с това ЕГН.")
        if handover_full_name(existing).casefold() == full_name:
            raise ValueError("В тази петролна база вече има лице с това име.")
    return result
