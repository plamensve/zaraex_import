"""Editing controls for loading records and persistent nomenclatures."""

import tkinter as tk
from tkinter import ttk, messagebox
from addresses import AddressFields, validate_address


FIELDS = {
    "products": [("name", "Наименование"), ("link_code", "Код за връзка"), ("kn_code", "Код по КН"), ("fuel_kind", "Вид гориво"), ("helper_bj", "BJ helper")],
    "transport_companies": [("name", "Фирма"), ("eik", "ЕИК")],
    "vehicles": [("registration", "МПС"), ("company_eik", "Транспортна фирма")],
    "drivers": [("name", "Име"), ("egn", "ЕГН"), ("company_eik", "Транспортна фирма")],
    "bases": [("name", "Петролна база"), ("eik", "ЕИК")],
}


def prepare_settings_edit(data, collection, index, changes):
    """Validate a replacement while retaining imported metadata."""
    updated = dict(data[collection][index])
    updated.update(changes)
    required = {
        "products": ("name",),
        "transport_companies": ("name", "eik"),
        "vehicles": ("registration", "company_eik"),
        "drivers": ("name", "egn", "company_eik"),
        "bases": ("name", "eik"),
    }[collection]
    if any(not updated.get(key) for key in required):
        raise ValueError("Попълни задължителните полета.")
    if collection == "products":
        helper = updated.get("helper_bj")
        updated["helper_bj"] = int(helper) if helper not in (None, "") else None
    if "company_eik" in updated and not any(c["eik"] == updated["company_eik"] for c in data["transport_companies"]):
        raise ValueError("Избери съществуваща транспортна фирма.")
    if collection == "bases":
        updated["address"] = validate_address(updated.get("address", {}))
    others = [item for i, item in enumerate(data[collection]) if i != index]
    unique_keys = {
        "products": ("name", "link_code"),
        "transport_companies": ("name", "eik"),
        "bases": ("name",),
    }.get(collection, ())
    if any(updated.get(key) and any(item.get(key) == updated[key] for item in others) for key in unique_keys):
        raise ValueError("Вече има запис със същото име или код.")
    if collection in ("vehicles", "drivers"):
        key = "registration" if collection == "vehicles" else "name"
        if any(item.get(key) == updated[key] and item.get("company_eik") == updated["company_eik"] for item in others):
            raise ValueError("Вече има такъв запис към избраната фирма.")
    return updated


def apply_settings_edit(data, collection, index, updated):
    old = data[collection][index]
    if collection == "transport_companies" and old["eik"] != updated["eik"]:
        for related in ("vehicles", "drivers"):
            for item in data[related]:
                if item.get("company_eik") == old["eik"]:
                    item["company_eik"] = updated["eik"]
    data[collection][index] = updated


class SettingsEditorMixin:
    def add_settings_actions(self, parent, collection, tree, delete_text):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(row, text="Редактирай избраното", command=lambda: self.edit_settings_item(collection, tree)).pack(side="left", padx=(0, 8))
        ttk.Button(row, text=delete_text, command=lambda: self.delete_settings_item(collection, tree)).pack(side="left")
        tree.bind("<Double-1>", lambda event: self.edit_settings_item(collection, tree))

    def edit_settings_item(self, collection, tree):
        selection = tree.selection()
        if len(selection) != 1:
            messagebox.showinfo("Редакция", "Избери един запис за редакция.")
            return
        index = int(selection[0])
        original = self.store.data[collection][index]
        dialog = tk.Toplevel(self)
        dialog.title("Редакция на запис")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        form = ttk.Frame(dialog, padding=18)
        form.pack(fill="both", expand=True)
        variables = {}
        companies = {f"{c['name']} · {c['eik']}": c["eik"] for c in self.store.data["transport_companies"]}
        for row, (key, label) in enumerate(FIELDS[collection]):
            value = original.get(key, "")
            if key == "company_eik":
                value = next((name for name, eik in companies.items() if eik == value), "")
            var = tk.StringVar(dialog, value="" if value is None else str(value))
            variables[key] = var
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            if key == "company_eik":
                entry = ttk.Combobox(form, textvariable=var, values=list(companies), state="readonly", width=65)
            else:
                entry = ttk.Entry(form, textvariable=var, width=68)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            if row == 0:
                entry.focus_set()

        address_fields = None
        if collection == "bases":
            address_fields = AddressFields(form, original.get("address"))
            address_fields.grid(row=len(variables), column=0, columnspan=2, sticky="ew", pady=(8, 0))

        def save():
            changes = {key: var.get().strip() for key, var in variables.items()}
            if "company_eik" in changes:
                changes["company_eik"] = companies.get(changes["company_eik"], "")
            try:
                if address_fields is not None:
                    changes["address"] = address_fields.get_address()
                updated = prepare_settings_edit(self.store.data, collection, index, changes)
            except ValueError as exc:
                messagebox.showerror("Невалидни данни", str(exc), parent=dialog)
                return
            self.cancel_record_edit()
            apply_settings_edit(self.store.data, collection, index, updated)
            self.save_and_refresh()
            dialog.destroy()

        buttons = ttk.Frame(form)
        buttons.grid(row=len(variables) + (1 if address_fields is not None else 0), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Отказ", command=dialog.destroy).pack(side="left", padx=8)
        ttk.Button(buttons, text="Запази промените", command=save).pack(side="left")
        dialog.bind("<Escape>", lambda event: dialog.destroy())

    def record_form_variables(self):
        return {key: getattr(self, key + "_var") for key in (
            "date", "ukn", "add", "quantity", "zara", "product", "company", "vehicle", "driver", "base"
        )}

    def edit_selected_record(self):
        selection = self.records_tree.selection()
        if len(selection) != 1:
            messagebox.showinfo("Редакция", "Избери едно товарене за редакция.")
            return
        index = int(self.records_tree.item(selection[0], "values")[0]) - 1
        if self.editing_record_index is not None:
            self.cancel_record_edit()
        self.record_form_before_edit = {key: var.get() for key, var in self.record_form_variables().items()}
        record = self.records[index]
        values = {
            "date": record["date"].strftime("%d.%m.%Y"), "ukn": record["ukn"],
            "add": record["add_no"], "quantity": str(record["quantity"]), "zara": record["zara_code"],
            "product": record["product_name"], "company": record["company_name"], "base": record["base_name"],
            "vehicle": record["vehicle"], "driver": record["driver_name"],
        }
        for key, var in self.record_form_variables().items():
            var.set(values[key])
        self.refresh_company_dependent_dropdowns()
        self.vehicle_var.set(values["vehicle"])
        self.driver_var.set(values["driver"])
        self.update_selection_info()
        self.editing_record_index = index
        self.record_save_button.configure(text="Запази промените")
        self.record_cancel_button.configure(state="normal")
        self.record_edit_status.set(f"Редакция на товарене № {index + 1}. Промени полетата горе и натисни „Запази промените“.")

    def finish_record_edit(self):
        self.editing_record_index = None
        self.record_save_button.configure(text="Добави товарене")
        self.record_cancel_button.configure(state="disabled")
        self.record_edit_status.set("")

    def cancel_record_edit(self):
        if self.editing_record_index is None:
            return
        for key, var in self.record_form_variables().items():
            var.set(self.record_form_before_edit[key])
        self.refresh_company_dependent_dropdowns()
        self.update_selection_info()
        self.finish_record_edit()
