import sys
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import math

from excel_export import ExcelWorkbook
from product_catalog import CATALOG_VERSION, load_catalog, migrate_catalog
from settings_editor import SettingsEditorMixin
from addresses import AddressFields, validate_address, format_address


APP_TITLE = "ZaraEx Import Generator"
DATA_FILE = "zaraex_data.json"


# ============================================================
# DEFAULT DATA
# ============================================================
# Кодът за връзка е вътрешният ключ между продукта в приложението
# и продуктова номенклатура/логика за ZaraEx.
#
# Не е нужно да е видим в основния екран. Съхранява се към продукта
# и се използва при генерирането на реда за съответния продукт.
#
# Добавяй/редактирай реалните кодове от втория таб "Настройки".
# ============================================================

DEFAULT_DATA = {
    "product_catalog_version": CATALOG_VERSION,
    "products": load_catalog(),
    "transport_companies": [
        {
            "name": "СИ-ТРАНС БЪЛГАРИЯ ЕООД",
            "eik": "204591346",
        }
    ],
    "vehicles": [
        {
            "registration": "В9261РА",
            "company_eik": "204591346",
        }
    ],
    "drivers": [
        {
            "name": "Тодор Димитров Попов",
            "egn": "7909031040",
            "company_eik": "204591346",
        }
    ],
    "bases": [
        {
            "name": "ТОПЛИВО АД",
            "eik": "831924394",
        }
    ],
}


# ============================================================
# EADD STRUCTURE
# 63 columns through BK.
# Empty header names are intentional helper columns.
# ============================================================

EADD_HEADERS = [
    "УКН",                              # A
    "Адд No",                           # B
    "Дата",                             # C
    "Вид гориво",                       # D
    "Код по КН",                        # E
    "Наименование на горивото",         # F
    "Количество",                       # G
    "Доставчик име",                    # H
    "Доставчик ЕИК",                    # I
    "Област",                           # J
    "Област код",                       # K
    "Община",                           # L
    "Община код",                       # M
    "Населено място",                   # N
    "Населено място код",               # O
    "Район",                            # P
    "Район код",                        # Q
    "Адрес на обекта за доставка",      # R
    "Наименование на обекта за доставка", # S
    "Регистрационен номер в НАП",       # T
    "Транспортна фирма",                # U
    "Транспортна фирма ЕИК",            # V
    "Вид транспорт",                    # W
    "Влекач ремарке",                   # X
    "Приел горивото",                   # Y
    "Приел горивото ЕГН",               # Z
    "Предал горивото",                  # AA
    "Предал горивото ЕГН",              # AB
    "Място на получаване на горивото",  # AC
    "Код в ЛУКОЙЛ",                     # AD
    "Област",                           # AE
    "Област код",                       # AF
    "Община",                           # AG
    "Община код",                       # AH
    "Населено място",                   # AI
    "Населено място код",               # AJ
    "Район",                            # AK
    "Район код",                        # AL
    "Адрес на място на получаване",     # AM
    "Получател",                        # AN
    "Код на клиент",                    # AO
    "ЕИК на Обект",                     # AP
    "TaxDocumentDate",                  # AQ
    "Държава търговец",                 # AR
    "ЕИК на Издател",                   # AS
    "DateOfPublishing",                 # AT
    "Документ No",                      # AU
    "Документ дата",                    # AV
    "Сертификат No",                    # AW
    "Сертификат дата",                  # AX
    "Партида на гориво",                # AY
    "Допълнителна информация",          # AZ
    "Маса КГ",                          # BA
    "Направление",                      # BB
    "Основно гориво Л",                 # BC
    "Плащане дни отср.",                # BD
    "",                                 # BE
    "",                                 # BF
    "",                                 # BG
    "",                                 # BH
    "",                                 # BI
    "",                                 # BJ helper
    "",                                 # BK helper
]


class DataStore:
    def __init__(self):
        # One-file EXEs unpack __file__ to a temporary directory.
        if getattr(sys, "frozen", False):
            user_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "ZaraExImport",
            )
            os.makedirs(user_dir, exist_ok=True)
            self.path = os.path.join(user_dir, DATA_FILE)
            if not os.path.exists(self.path):
                for legacy in (
                    os.path.join(os.path.dirname(sys.executable), DATA_FILE),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), DATA_FILE),
                ):
                    if os.path.isfile(legacy):
                        import shutil
                        shutil.copy2(legacy, self.path)
                        break
        else:
            self.path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), DATA_FILE
            )
        self.data = self.load()

    def load(self):
        if not os.path.exists(self.path):
            return json.loads(json.dumps(DEFAULT_DATA, ensure_ascii=False))

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # ensure all collections exist
            for key, default_value in DEFAULT_DATA.items():
                if key != "product_catalog_version":
                    data.setdefault(key, default_value)

            if migrate_catalog(data):
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        except Exception:
            return json.loads(json.dumps(DEFAULT_DATA, ensure_ascii=False))

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


class ZaraExApp(SettingsEditorMixin, tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1520x900")
        self.minsize(1200, 720)

        self.store = DataStore()
        self.records = self.load_draft_records()
        self.editing_record_index = None

        self.setup_styles()
        self.build_ui()
        self.refresh_all_settings_tables()
        self.refresh_main_dropdowns()
        self.refresh_records_table()

    @staticmethod
    def serialize_draft_record(record):
        result = dict(record)
        result["date"] = record["date"].isoformat()
        return result

    def load_draft_records(self):
        """Restore the pending declarations, keeping a bad row from crashing startup."""
        from datetime import datetime
        records = []
        for stored in self.store.data.get("draft_records", []):
            try:
                record = dict(stored)
                record["date"] = datetime.fromisoformat(record["date"])
                record["quantity"] = float(record["quantity"])
                records.append(record)
            except (KeyError, TypeError, ValueError):
                continue
        return records

    def save_draft_records(self):
        self.store.data["draft_records"] = [self.serialize_draft_record(r) for r in self.records]
        self.store.save()

    # ========================================================
    # STYLES
    # ========================================================

    def setup_styles(self):
        style = ttk.Style(self)

        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=30)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold")
        )

    # ========================================================
    # MAIN UI
    # ========================================================

    def build_ui(self):
        header = tk.Frame(self, bg="#17365D", height=68)
        header.pack(fill="x")

        tk.Label(
            header,
            text="ZaraEx Import Generator",
            bg="#17365D",
            fg="white",
            font=("Segoe UI", 20, "bold")
        ).pack(side="left", padx=24, pady=17)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=14)

        self.main_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="Товарения")
        self.notebook.add(self.settings_tab, text="Настройки")

        self.build_main_tab()
        self.build_settings_tab()

    # ========================================================
    # MAIN TAB
    # ========================================================

    def build_main_tab(self):
        form = ttk.LabelFrame(
            self.main_tab,
            text="Ново товарене",
            padding=14
        )
        form.pack(fill="x", padx=10, pady=(10, 8))

        self.date_var = tk.StringVar(
            value=datetime.now().strftime("%d.%m.%Y")
        )
        self.ukn_var = tk.StringVar()
        self.add_var = tk.StringVar()
        self.quantity_var = tk.StringVar()
        self.zara_var = tk.StringVar()

        self.product_var = tk.StringVar()
        self.company_var = tk.StringVar()
        self.vehicle_var = tk.StringVar()
        self.driver_var = tk.StringVar()
        self.base_var = tk.StringVar()

        # Row 0
        self.add_entry(form, "Дата", self.date_var, 0, 0, 16)
        self.add_entry(form, "УКН", self.ukn_var, 0, 2, 24)
        self.add_entry(form, "ADD №", self.add_var, 0, 4, 18)
        self.add_entry(form, "Количество (л.)", self.quantity_var, 0, 6, 16)
        self.add_entry(form, "Код ЗАРА", self.zara_var, 0, 8, 18)

        # Row 1 product
        ttk.Label(form, text="Продукт").grid(
            row=1, column=0, sticky="w", padx=5, pady=8
        )

        self.product_combo = ttk.Combobox(
            form,
            textvariable=self.product_var,
            state="readonly",
            width=55
        )
        self.product_combo.grid(
            row=1, column=1, columnspan=3,
            sticky="ew", padx=(0, 15), pady=8
        )

        ttk.Label(form, text="Петролна база").grid(
            row=1, column=4, sticky="w", padx=5, pady=8
        )

        self.base_combo = ttk.Combobox(
            form,
            textvariable=self.base_var,
            state="readonly",
            width=28
        )
        self.base_combo.grid(
            row=1, column=5,
            sticky="ew", padx=(0, 15), pady=8
        )

        ttk.Label(form, text="Транспортна фирма").grid(
            row=1, column=6, sticky="w", padx=5, pady=8
        )

        self.company_combo = ttk.Combobox(
            form,
            textvariable=self.company_var,
            state="readonly",
            width=30
        )
        self.company_combo.grid(
            row=1, column=7,
            sticky="ew", padx=(0, 15), pady=8
        )
        self.company_combo.bind(
            "<<ComboboxSelected>>",
            self.on_company_changed
        )

        # Row 2
        ttk.Label(form, text="МПС").grid(
            row=2, column=0, sticky="w", padx=5, pady=8
        )

        self.vehicle_combo = ttk.Combobox(
            form,
            textvariable=self.vehicle_var,
            state="readonly",
            width=24
        )
        self.vehicle_combo.grid(
            row=2, column=1,
            sticky="ew", padx=(0, 15), pady=8
        )

        ttk.Label(form, text="Шофьор").grid(
            row=2, column=2, sticky="w", padx=5, pady=8
        )

        self.driver_combo = ttk.Combobox(
            form,
            textvariable=self.driver_var,
            state="readonly",
            width=30
        )
        self.driver_combo.grid(
            row=2, column=3,
            sticky="ew", padx=(0, 15), pady=8
        )

        self.record_save_button = ttk.Button(
            form,
            text="Добави товарене",
            style="Primary.TButton",
            command=self.add_record
        )
        self.record_save_button.grid(
            row=2, column=8, columnspan=2,
            sticky="e", padx=10, pady=8
        )

        # Info line
        self.selection_info_var = tk.StringVar()
        ttk.Label(
            form,
            textvariable=self.selection_info_var
        ).grid(
            row=3, column=0, columnspan=10,
            sticky="w", padx=5, pady=(4, 0)
        )

        self.product_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_selection_info()
        )
        self.base_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_selection_info()
        )
        self.vehicle_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_selection_info()
        )
        self.driver_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.update_selection_info()
        )

        # Records table
        table_frame = ttk.LabelFrame(
            self.main_tab,
            text="Товарения",
            padding=10
        )
        table_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=8
        )

        columns = (
            "n",
            "date",
            "ukn",
            "add",
            "product",
            "link_code",
            "qty",
            "base",
            "company",
            "vehicle",
            "driver",
            "zara",
        )

        self.records_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )

        headings = {
            "n": "№",
            "date": "Дата",
            "ukn": "УКН",
            "add": "ADD №",
            "product": "Продукт",
            "link_code": "Код за връзка",
            "qty": "Литри",
            "base": "Петролна база",
            "company": "Транспортна фирма",
            "vehicle": "МПС",
            "driver": "Шофьор",
            "zara": "Код ЗАРА",
        }

        widths = {
            "n": 45,
            "date": 90,
            "ukn": 165,
            "add": 115,
            "product": 300,
            "link_code": 110,
            "qty": 80,
            "base": 180,
            "company": 220,
            "vehicle": 135,
            "driver": 200,
            "zara": 120,
        }

        for c in columns:
            self.records_tree.heading(c, text=headings[c])
            self.records_tree.column(
                c,
                width=widths[c],
                anchor="center"
            )

        vs = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.records_tree.yview
        )
        hs = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.records_tree.xview
        )

        self.records_tree.configure(
            yscrollcommand=vs.set,
            xscrollcommand=hs.set
        )

        self.records_tree.grid(
            row=0, column=0, sticky="nsew"
        )
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.records_tree.bind("<Double-1>", lambda event: self.edit_selected_record())
        actions_menu = tk.Menu(self.records_tree, tearoff=0)
        actions_menu.add_command(label="Редактирай декларацията", command=self.edit_selected_record)
        actions_menu.add_command(label="Премахни декларацията", command=self.delete_selected_records)
        def show_record_actions(event):
            row = self.records_tree.identify_row(event.y)
            if row:
                self.records_tree.selection_set(row)
                actions_menu.tk_popup(event.x_root, event.y_root)
                actions_menu.grab_release()
        self.records_tree.bind("<Button-3>", show_record_actions)
        self.record_edit_status = tk.StringVar()
        ttk.Label(self.main_tab, textvariable=self.record_edit_status).pack(anchor="w", padx=12)

        bottom = ttk.Frame(self.main_tab)
        bottom.pack(fill="x", padx=10, pady=(0, 12))

        ttk.Button(bottom, text="Редактирай избраното", command=self.edit_selected_record).pack(side="left", padx=(0, 8))
        self.record_cancel_button = ttk.Button(bottom, text="Откажи редакцията", command=self.cancel_record_edit, state="disabled")
        self.record_cancel_button.pack(side="left", padx=(0, 8))

        ttk.Button(
            bottom,
            text="Изтрий избраното",
            command=self.delete_selected_records
        ).pack(side="left")

        ttk.Button(
            bottom,
            text="Изчисти всички",
            command=self.clear_records
        ).pack(side="left", padx=8)

        ttk.Button(
            bottom,
            text="ГЕНЕРИРАЙ ФАЙЛ",
            style="Primary.TButton",
            command=self.export_xls
        ).pack(side="right")

    @staticmethod
    def add_entry(parent, label, variable, row, col, width):
        ttk.Label(parent, text=label).grid(
            row=row, column=col, sticky="w", padx=5, pady=8
        )
        ttk.Entry(
            parent,
            textvariable=variable,
            width=width
        ).grid(
            row=row, column=col + 1,
            sticky="ew", padx=(0, 15), pady=8
        )

    # ========================================================
    # SETTINGS TAB
    # ========================================================

    def build_settings_tab(self):
        intro = ttk.Label(
            self.settings_tab,
            text=(
                "Тук се поддържат номенклатурите. "
                "Промените се запазват автоматично и се използват в таб „Товарения“."
            )
        )
        intro.pack(anchor="w", padx=14, pady=(14, 8))

        self.settings_notebook = ttk.Notebook(self.settings_tab)
        self.settings_notebook.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12)
        )

        self.products_settings = ttk.Frame(self.settings_notebook)
        self.companies_settings = ttk.Frame(self.settings_notebook)
        self.vehicles_settings = ttk.Frame(self.settings_notebook)
        self.drivers_settings = ttk.Frame(self.settings_notebook)
        self.bases_settings = ttk.Frame(self.settings_notebook)

        self.settings_notebook.add(
            self.products_settings,
            text="Продукти"
        )
        self.settings_notebook.add(
            self.companies_settings,
            text="Транспортни фирми"
        )
        self.settings_notebook.add(
            self.vehicles_settings,
            text="МПС"
        )
        self.settings_notebook.add(
            self.drivers_settings,
            text="Шофьори"
        )
        self.settings_notebook.add(
            self.bases_settings,
            text="Петролни бази"
        )

        self.build_products_settings()
        self.build_companies_settings()
        self.build_vehicles_settings()
        self.build_drivers_settings()
        self.build_bases_settings()

    # ========================================================
    # PRODUCTS
    # ========================================================

    def build_products_settings(self):
        frame = self.products_settings

        form = ttk.LabelFrame(frame, text="Добави продукт", padding=12)
        form.pack(fill="x", padx=10, pady=10)

        self.p_name = tk.StringVar()
        self.p_link = tk.StringVar()
        self.p_kn = tk.StringVar()
        self.p_kind = tk.StringVar(value="Газьол - немаркиран")
        self.p_helper = tk.StringVar()

        self.add_entry(form, "Наименование", self.p_name, 0, 0, 50)
        self.add_entry(form, "Код за връзка", self.p_link, 0, 2, 18)
        self.add_entry(form, "Код по КН", self.p_kn, 0, 4, 18)
        self.add_entry(form, "Вид гориво", self.p_kind, 1, 0, 30)
        self.add_entry(form, "BJ helper", self.p_helper, 1, 2, 12)

        ttk.Button(
            form,
            text="Добави продукт",
            command=self.add_product
        ).grid(row=1, column=5, padx=10, pady=8)

        self.products_tree = self.make_settings_tree(
            frame,
            (
                ("name", "Продукт", 520),
                ("link", "Код за връзка", 150),
                ("kn", "Код по КН", 140),
                ("kind", "Вид гориво", 220),
                ("helper", "BJ helper", 100),
            )
        )

        self.add_settings_actions(frame, "products", self.products_tree, "Изтрий избрания продукт")

    # ========================================================
    # COMPANIES
    # ========================================================

    def build_companies_settings(self):
        frame = self.companies_settings

        form = ttk.LabelFrame(
            frame,
            text="Добави транспортна фирма",
            padding=12
        )
        form.pack(fill="x", padx=10, pady=10)

        self.c_name = tk.StringVar()
        self.c_eik = tk.StringVar()

        self.add_entry(form, "Фирма", self.c_name, 0, 0, 40)
        self.add_entry(form, "ЕИК", self.c_eik, 0, 2, 18)

        ttk.Button(
            form,
            text="Добави фирма",
            command=self.add_company
        ).grid(row=0, column=4, padx=10, pady=8)

        self.companies_tree = self.make_settings_tree(
            frame,
            (
                ("name", "Транспортна фирма", 520),
                ("eik", "ЕИК", 180),
            )
        )

        self.add_settings_actions(frame, "transport_companies", self.companies_tree, "Изтрий избраната фирма")

    # ========================================================
    # VEHICLES
    # ========================================================

    def build_vehicles_settings(self):
        frame = self.vehicles_settings

        form = ttk.LabelFrame(frame, text="Добави МПС", padding=12)
        form.pack(fill="x", padx=10, pady=10)

        self.v_reg = tk.StringVar()
        self.v_company = tk.StringVar()

        self.add_entry(form, "Рег. № / влекач-ремарке", self.v_reg, 0, 0, 30)

        ttk.Label(form, text="Транспортна фирма").grid(
            row=0, column=2, sticky="w", padx=5, pady=8
        )

        self.v_company_combo = ttk.Combobox(
            form,
            textvariable=self.v_company,
            state="readonly",
            width=35
        )
        self.v_company_combo.grid(
            row=0, column=3, sticky="ew",
            padx=(0, 15), pady=8
        )

        ttk.Button(
            form,
            text="Добави МПС",
            command=self.add_vehicle
        ).grid(row=0, column=4, padx=10, pady=8)

        self.vehicles_tree = self.make_settings_tree(
            frame,
            (
                ("reg", "МПС", 260),
                ("company", "Транспортна фирма", 520),
                ("eik", "ЕИК", 180),
            )
        )

        self.add_settings_actions(frame, "vehicles", self.vehicles_tree, "Изтрий избраното МПС")

    # ========================================================
    # DRIVERS
    # ========================================================

    def build_drivers_settings(self):
        frame = self.drivers_settings

        form = ttk.LabelFrame(frame, text="Добави шофьор", padding=12)
        form.pack(fill="x", padx=10, pady=10)

        self.d_name = tk.StringVar()
        self.d_egn = tk.StringVar()
        self.d_company = tk.StringVar()

        self.add_entry(form, "Име", self.d_name, 0, 0, 35)
        self.add_entry(form, "ЕГН", self.d_egn, 0, 2, 18)

        ttk.Label(form, text="Транспортна фирма").grid(
            row=1, column=0, sticky="w", padx=5, pady=8
        )

        self.d_company_combo = ttk.Combobox(
            form,
            textvariable=self.d_company,
            state="readonly",
            width=35
        )
        self.d_company_combo.grid(
            row=1, column=1, sticky="ew",
            padx=(0, 15), pady=8
        )

        ttk.Button(
            form,
            text="Добави шофьор",
            command=self.add_driver
        ).grid(row=1, column=3, padx=10, pady=8)

        self.drivers_tree = self.make_settings_tree(
            frame,
            (
                ("name", "Шофьор", 420),
                ("egn", "ЕГН", 170),
                ("company", "Транспортна фирма", 420),
                ("eik", "ЕИК", 180),
            )
        )

        self.add_settings_actions(frame, "drivers", self.drivers_tree, "Изтрий избрания шофьор")

    # ========================================================
    # BASES
    # ========================================================

    def build_bases_settings(self):
        frame = self.bases_settings

        form = ttk.LabelFrame(frame, text="Добави петролна база", padding=12)
        form.pack(fill="x", padx=10, pady=10)

        self.b_name = tk.StringVar()
        self.b_eik = tk.StringVar()
        self.b_link_code = tk.StringVar()

        self.add_entry(form, "Петролна база", self.b_name, 0, 0, 40)
        self.add_entry(form, "ЕИК", self.b_eik, 0, 2, 18)

        self.add_entry(form, "Код за връзка", self.b_link_code, 1, 0, 18)

        self.base_address_fields = AddressFields(form)
        self.base_address_fields.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(8, 0))

        ttk.Button(
            form,
            text="Добави база",
            command=self.add_base
        ).grid(row=0, column=4, padx=10, pady=8)

        self.bases_tree = self.make_settings_tree(
            frame,
            (
                ("name", "Петролна база", 320),
                ("eik", "ЕИК", 140),
                ("link_code", "Код за връзка", 140),
                ("address", "Адрес", 400),
                ("city_code", "Код на населено място", 180),
            )
        )

        self.add_settings_actions(frame, "bases", self.bases_tree, "Изтрий избраната база")

    @staticmethod
    def make_settings_tree(parent, columns):
        wrap = ttk.Frame(parent)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        ids = tuple(c[0] for c in columns)

        tree = ttk.Treeview(
            wrap,
            columns=ids,
            show="headings",
            selectmode="browse"
        )

        for col_id, title, width in columns:
            tree.heading(col_id, text=title)
            tree.column(col_id, width=width, anchor="center")

        vs = ttk.Scrollbar(
            wrap,
            orient="vertical",
            command=tree.yview
        )
        tree.configure(yscrollcommand=vs.set)

        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        return tree

    @staticmethod
    def add_delete_button(parent, text, command):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(
            row,
            text=text,
            command=command
        ).pack(side="left")

    # ========================================================
    # SETTINGS CRUD
    # ========================================================

    def add_product(self):
        name = self.p_name.get().strip()
        link = self.p_link.get().strip()
        kn = self.p_kn.get().strip()
        kind = self.p_kind.get().strip()

        if not name or not link or not kn:
            messagebox.showerror(
                "Грешка",
                "За продукта са задължителни: "
                "Наименование, Код за връзка и Код по КН."
            )
            return

        if any(
            p["link_code"] == link
            for p in self.store.data["products"]
        ):
            messagebox.showerror(
                "Грешка",
                "Вече има продукт с този код за връзка."
            )
            return

        helper = None
        if self.p_helper.get().strip():
            try:
                helper = int(self.p_helper.get().strip())
            except ValueError:
                messagebox.showerror(
                    "Грешка",
                    "BJ helper трябва да бъде цяло число."
                )
                return

        self.store.data["products"].append({
            "name": name,
            "link_code": link,
            "kn_code": kn,
            "fuel_kind": kind or "Газьол - немаркиран",
            "helper_bj": helper,
        })

        self.save_and_refresh()

        self.p_name.set("")
        self.p_link.set("")
        self.p_kn.set("")
        self.p_helper.set("")

    def add_company(self):
        name = self.c_name.get().strip()
        eik = self.c_eik.get().strip()

        if not name or not eik:
            messagebox.showerror(
                "Грешка",
                "Въведи име на фирма и ЕИК."
            )
            return

        if any(
            c["eik"] == eik
            for c in self.store.data["transport_companies"]
        ):
            messagebox.showerror(
                "Грешка",
                "Вече има транспортна фирма с този ЕИК."
            )
            return

        self.store.data["transport_companies"].append({
            "name": name,
            "eik": eik,
        })

        self.save_and_refresh()
        self.c_name.set("")
        self.c_eik.set("")

    def add_vehicle(self):
        reg = self.v_reg.get().strip()
        company_name = self.v_company.get().strip()

        company = self.get_company_by_name(company_name)

        if not reg or not company:
            messagebox.showerror(
                "Грешка",
                "Въведи МПС и избери транспортна фирма."
            )
            return

        self.store.data["vehicles"].append({
            "registration": reg,
            "company_eik": company["eik"],
        })

        self.save_and_refresh()
        self.v_reg.set("")

    def add_driver(self):
        name = self.d_name.get().strip()
        egn = self.d_egn.get().strip()
        company_name = self.d_company.get().strip()

        company = self.get_company_by_name(company_name)

        if not name or not egn or not company:
            messagebox.showerror(
                "Грешка",
                "Въведи име, ЕГН и транспортна фирма."
            )
            return

        self.store.data["drivers"].append({
            "name": name,
            "egn": egn,
            "company_eik": company["eik"],
        })

        self.save_and_refresh()
        self.d_name.set("")
        self.d_egn.set("")

    def add_base(self):
        name = self.b_name.get().strip()
        eik = self.b_eik.get().strip()

        if not name or not eik:
            messagebox.showerror(
                "Грешка",
                "Въведи име на петролна база и ЕИК."
            )
            return

        try:
            address = self.base_address_fields.get_address()
        except ValueError as exc:
            messagebox.showerror("Невалиден адрес", str(exc))
            return
        if any(base.get("name") == name for base in self.store.data["bases"]):
            messagebox.showerror("Грешка", "Вече има база с това име.")
            return
        self.store.data["bases"].append({
            "name": name,
            "eik": eik,
            "address": address,
            "link_code": self.b_link_code.get().strip(),
        })

        self.save_and_refresh()
        self.b_name.set("")
        self.b_eik.set("")
        self.b_link_code.set("")
        self.base_address_fields.clear()

    def delete_settings_item(self, collection, tree):
        selected = tree.selection()

        if not selected:
            return

        index = int(selected[0])

        if index < 0 or index >= len(self.store.data[collection]):
            return

        prompt = "Да бъде ли изтрит избраният запис?"
        if collection == "transport_companies":
            prompt += "\nЩе бъдат изтрити и свързаните МПС и шофьори."
        if not messagebox.askyesno("Потвърждение", prompt):
            return

        self.cancel_record_edit()
        deleted = self.store.data[collection].pop(index)

        # If a company is deleted, orphaned vehicles/drivers are also removed.
        if collection == "transport_companies":
            eik = deleted["eik"]

            self.store.data["vehicles"] = [
                v for v in self.store.data["vehicles"]
                if v.get("company_eik") != eik
            ]

            self.store.data["drivers"] = [
                d for d in self.store.data["drivers"]
                if d.get("company_eik") != eik
            ]

        self.save_and_refresh()

    def save_and_refresh(self):
        self.store.save()
        self.refresh_all_settings_tables()
        self.refresh_main_dropdowns()

    # ========================================================
    # SETTINGS TABLES
    # ========================================================

    def refresh_all_settings_tables(self):
        # Products
        self.clear_tree(self.products_tree)

        for i, p in enumerate(self.store.data["products"]):
            self.products_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    p.get("name", ""),
                    p.get("link_code", ""),
                    p.get("kn_code", ""),
                    p.get("fuel_kind", ""),
                    p.get("helper_bj", ""),
                )
            )

        # Companies
        self.clear_tree(self.companies_tree)

        for i, c in enumerate(self.store.data["transport_companies"]):
            self.companies_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(c.get("name", ""), c.get("eik", ""))
            )

        # Vehicles
        self.clear_tree(self.vehicles_tree)

        for i, v in enumerate(self.store.data["vehicles"]):
            company = self.get_company_by_eik(
                v.get("company_eik", "")
            )

            self.vehicles_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    v.get("registration", ""),
                    company.get("name", "") if company else "",
                    v.get("company_eik", ""),
                )
            )

        # Drivers
        self.clear_tree(self.drivers_tree)

        for i, d in enumerate(self.store.data["drivers"]):
            company = self.get_company_by_eik(
                d.get("company_eik", "")
            )

            self.drivers_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    d.get("name", ""),
                    d.get("egn", ""),
                    company.get("name", "") if company else "",
                    d.get("company_eik", ""),
                )
            )

        # Bases
        self.clear_tree(self.bases_tree)

        for i, b in enumerate(self.store.data["bases"]):
            self.bases_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(b.get("name", ""), b.get("eik", ""), b.get("link_code", ""), format_address(b.get("address")), b.get("address", {}).get("city_code", ""))
            )

        companies = [
            c["name"]
            for c in self.store.data["transport_companies"]
        ]

        self.v_company_combo["values"] = companies
        self.d_company_combo["values"] = companies

        if companies:
            if self.v_company.get() not in companies:
                self.v_company.set(companies[0])

            if self.d_company.get() not in companies:
                self.d_company.set(companies[0])
        else:
            self.v_company.set("")
            self.d_company.set("")

    @staticmethod
    def clear_tree(tree):
        for item in tree.get_children():
            tree.delete(item)

    # ========================================================
    # MAIN DROPDOWNS
    # ========================================================

    def refresh_main_dropdowns(self):
        products = [
            p["name"]
            for p in self.store.data["products"]
        ]

        companies = [
            c["name"]
            for c in self.store.data["transport_companies"]
        ]

        bases = [
            b["name"]
            for b in self.store.data["bases"]
        ]

        self.product_combo["values"] = products
        self.company_combo["values"] = companies
        self.base_combo["values"] = bases

        if self.product_var.get() not in products:
            self.product_var.set(products[0] if products else "")

        if self.company_var.get() not in companies:
            self.company_var.set(companies[0] if companies else "")

        if self.base_var.get() not in bases:
            self.base_var.set(bases[0] if bases else "")

        self.refresh_company_dependent_dropdowns()
        self.update_selection_info()

    def on_company_changed(self, event=None):
        self.refresh_company_dependent_dropdowns()
        self.update_selection_info()

    def refresh_company_dependent_dropdowns(self):
        company = self.get_company_by_name(
            self.company_var.get()
        )

        if not company:
            self.vehicle_combo["values"] = []
            self.driver_combo["values"] = []
            self.vehicle_var.set("")
            self.driver_var.set("")
            return

        eik = company["eik"]

        vehicles = [
            v["registration"]
            for v in self.store.data["vehicles"]
            if v.get("company_eik") == eik
        ]

        drivers = [
            d["name"]
            for d in self.store.data["drivers"]
            if d.get("company_eik") == eik
        ]

        self.vehicle_combo["values"] = vehicles
        self.driver_combo["values"] = drivers

        if vehicles:
            if self.vehicle_var.get() not in vehicles:
                self.vehicle_var.set(vehicles[0])
        else:
            self.vehicle_var.set("")

        if drivers:
            if self.driver_var.get() not in drivers:
                self.driver_var.set(drivers[0])
        else:
            self.driver_var.set("")

    def update_selection_info(self):
        product = self.get_product_by_name(
            self.product_var.get()
        )
        company = self.get_company_by_name(
            self.company_var.get()
        )
        driver = self.get_driver_by_name_and_company(
            self.driver_var.get(),
            company.get("eik", "") if company else ""
        )
        base = self.get_base_by_name(
            self.base_var.get()
        )

        parts = []

        if product:
            parts.append(
                f"Код за връзка: {product.get('link_code', '') or '-'}"
            )
            parts.append(
                f"КН: {product.get('kn_code', '') or '-'}"
            )

        if company:
            parts.append(
                f"ЕИК транспорт: {company.get('eik', '')}"
            )

        if driver:
            parts.append(
                f"ЕГН шофьор: {driver.get('egn', '')}"
            )

        if base:
            parts.append(
                f"ЕИК база: {base.get('eik', '')}"
            )
            if base.get("address"):
                parts.append(format_address(base["address"]))

        self.selection_info_var.set("   |   ".join(parts))

    # ========================================================
    # LOOKUPS
    # ========================================================

    def get_product_by_name(self, name):
        for p in self.store.data["products"]:
            if p.get("name") == name:
                return p
        return None

    def get_company_by_name(self, name):
        for c in self.store.data["transport_companies"]:
            if c.get("name") == name:
                return c
        return None

    def get_company_by_eik(self, eik):
        for c in self.store.data["transport_companies"]:
            if c.get("eik") == eik:
                return c
        return None

    def get_driver_by_name_and_company(self, name, company_eik):
        for d in self.store.data["drivers"]:
            if (
                d.get("name") == name
                and d.get("company_eik") == company_eik
            ):
                return d
        return None

    def get_base_by_name(self, name):
        for b in self.store.data["bases"]:
            if b.get("name") == name:
                return b
        return None

    # ========================================================
    # RECORDS
    # ========================================================

    def add_record(self):
        try:
            date_value = datetime.strptime(
                self.date_var.get().strip(),
                "%d.%m.%Y"
            )
        except ValueError:
            messagebox.showerror(
                "Грешка",
                "Датата трябва да е във формат ДД.ММ.ГГГГ."
            )
            return

        ukn = self.ukn_var.get().strip()
        add_no = self.add_var.get().strip()
        qty_text = self.quantity_var.get().strip().replace(",", ".")
        zara_code = self.zara_var.get().strip()

        product = self.get_product_by_name(
            self.product_var.get()
        )
        company = self.get_company_by_name(
            self.company_var.get()
        )
        base = self.get_base_by_name(
            self.base_var.get()
        )

        if not ukn:
            messagebox.showerror("Грешка", "Въведи УКН.")
            return

        if not add_no:
            messagebox.showerror("Грешка", "Въведи ADD №.")
            return

        try:
            quantity = float(qty_text)
            if not math.isfinite(quantity) or quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Грешка",
                "Количеството трябва да бъде положително число."
            )
            return

        if not product:
            messagebox.showerror(
                "Грешка",
                "Избери продукт."
            )
            return

        if not product.get("link_code"):
            messagebox.showerror(
                "Липсва код за връзка",
                "Избраният продукт няма зададен код за връзка.\n"
                "В изходната таблица някои кодове са празни. "
                "Избери продукт с код или добави реалния код в Настройки → Продукти."
            )
            return

        if not company:
            messagebox.showerror(
                "Грешка",
                "Избери транспортна фирма."
            )
            return

        vehicle = self.vehicle_var.get().strip()
        driver_name = self.driver_var.get().strip()

        driver = self.get_driver_by_name_and_company(
            driver_name,
            company["eik"]
        )

        if not any(v.get("registration") == vehicle and v.get("company_eik") == company["eik"] for v in self.store.data["vehicles"]):
            messagebox.showerror(
                "Грешка",
                "Избери МПС към избраната транспортна фирма."
            )
            return

        if not driver:
            messagebox.showerror(
                "Грешка",
                "Избери шофьор."
            )
            return

        if not base:
            messagebox.showerror(
                "Грешка",
                "Избери петролна база."
            )
            return

        try:
            base_address = validate_address(base.get("address", {}))
        except ValueError as exc:
            messagebox.showerror("Липсва адрес на базата", "Допълни адреса в Настройки → Петролни бази → Редактирай избраното.\n\n" + str(exc))
            return

        record = {
            "date": date_value,
            "ukn": ukn,
            "add_no": add_no,
            "quantity": quantity,
            "zara_code": zara_code,

            "product_name": product["name"],
            "product_link_code": product["link_code"],
            "kn_code": product["kn_code"],
            "fuel_kind": product.get(
                "fuel_kind",
                "Газьол - немаркиран"
            ),
            "helper_bj": product.get("helper_bj"),

            "company_name": company["name"],
            "company_eik": company["eik"],

            "vehicle": vehicle,

            "driver_name": driver["name"],
            "driver_egn": driver["egn"],

            "base_name": base["name"],
            "base_eik": base["eik"],
            "base_link_code": base.get("link_code", ""),
            "base_address": base_address,
        }

        if self.editing_record_index is None:
            self.records.append(record)
        else:
            self.records[self.editing_record_index] = record
            self.finish_record_edit()
        self.refresh_records_table()
        if hasattr(self, "save_draft_records"):
            self.save_draft_records()

        self.ukn_var.set("")
        self.add_var.set("")
        self.quantity_var.set("")
        self.zara_var.set("")

    def refresh_records_table(self):
        self.clear_tree(self.records_tree)

        for i, r in enumerate(self.records, start=1):
            qty = (
                int(r["quantity"])
                if r["quantity"].is_integer()
                else r["quantity"]
            )

            self.records_tree.insert(
                "",
                "end",
                values=(
                    i,
                    r["date"].strftime("%d.%m.%Y"),
                    r["ukn"],
                    r["add_no"],
                    r["product_name"],
                    r["product_link_code"],
                    qty,
                    r["base_name"],
                    r["company_name"],
                    r["vehicle"],
                    r["driver_name"],
                    r["zara_code"],
                )
            )

    def delete_selected_records(self):
        selected = self.records_tree.selection()

        if not selected:
            return

        indexes = []

        for item in selected:
            values = self.records_tree.item(item, "values")
            indexes.append(int(values[0]) - 1)

        if not messagebox.askyesno("Потвърждение", f"Да бъдат ли изтрити избраните товарения ({len(indexes)})?"):
            return
        self.cancel_record_edit()
        for idx in sorted(indexes, reverse=True):
            del self.records[idx]

        self.refresh_records_table()
        if hasattr(self, "save_draft_records"):
            self.save_draft_records()

    def clear_records(self):
        if not self.records:
            return

        if messagebox.askyesno(
            "Потвърждение",
            "Да бъдат ли изтрити всички товарения?"
        ):
            self.cancel_record_edit()
            self.records.clear()
            self.refresh_records_table()
            if hasattr(self, "save_draft_records"):
            self.save_draft_records()

    # ========================================================
    # EXPORT
    # ========================================================

    def export_xls(self):
        if not self.records:
            messagebox.showwarning(
                "Няма данни",
                "Добави поне едно товарене."
            )
            return

        file_date = self.records[0]["date"].strftime("%Y_%m_%d")

        output = filedialog.asksaveasfilename(
            title="Запази ZaraEx файла",
            defaultextension=".xls",
            initialfile=f"eadd_{file_date}.xls",
            filetypes=[("Excel 97-2003", "*.xls")]
        )

        if not output:
            return

        workbook = None
        try:
            workbook = ExcelWorkbook()
            eadd = workbook.sheet("EAdd")
            text_style = "@"
            date_style = "DD.MM.YYYY"
            number_style = "0.00"
            integer_style = "0"

            for row, r in enumerate(self.records, start=1):
                self.write_text(eadd, row, 0, r["ukn"], text_style)
                self.write_text(eadd, row, 1, r["add_no"], text_style)
                eadd.write(row, 2, r["date"], date_style)

                self.write_text(
                    eadd, row, 3,
                    r["fuel_kind"],
                    text_style
                )
                self.write_text(
                    eadd, row, 4,
                    r["kn_code"],
                    text_style
                )
                self.write_text(
                    eadd, row, 5,
                    r["product_name"],
                    text_style
                )

                if r["quantity"].is_integer():
                    eadd.write(
                        row, 6,
                        int(r["quantity"]),
                        integer_style
                    )
                else:
                    eadd.write(
                        row, 6,
                        r["quantity"],
                        number_style
                    )

                # Petroleum base is the supplier/base selected in Settings.
                self.write_text(
                    eadd, row, 7,
                    r["base_name"],
                    text_style
                )
                self.write_text(
                    eadd, row, 8,
                    r["base_eik"],
                    text_style
                )

                # Existing fixed location logic from the original working file.
                self.write_text(eadd, row, 9, "СОФИЯ (SOF)", text_style)
                self.write_text(eadd, row, 10, "SOF", text_style)
                self.write_text(eadd, row, 11, "СТОЛИЧНА", text_style)
                self.write_text(eadd, row, 12, "SOF46", text_style)
                self.write_text(eadd, row, 13, "СОФИЯ", text_style)
                self.write_text(eadd, row, 14, "68134", text_style)

                # Transport company
                self.write_text(
                    eadd, row, 20,
                    r["company_name"],
                    text_style
                )
                self.write_text(
                    eadd, row, 21,
                    r["company_eik"],
                    text_style
                )

                # Vehicle
                self.write_text(
                    eadd, row, 23,
                    r["vehicle"],
                    text_style
                )

                # Driver: accepted / handed over
                self.write_text(
                    eadd, row, 24,
                    r["driver_name"],
                    text_style
                )
                self.write_text(
                    eadd, row, 25,
                    r["driver_egn"],
                    text_style
                )
                self.write_text(
                    eadd, row, 26,
                    r["driver_name"],
                    text_style
                )
                self.write_text(
                    eadd, row, 27,
                    r["driver_egn"],
                    text_style
                )

                self.write_text(eadd, row, 29, r.get("base_link_code", ""), text_style)

                address = r["base_address"]
                for column, key in ((30, "region"), (31, "region_code"), (32, "municipality"), (33, "municipality_code"), (34, "city"), (35, "city_code")):
                    self.write_text(eadd, row, column, address[key], text_style)

                # Object EIK / issuer follows selected petroleum base.
                self.write_text(
                    eadd, row, 41,
                    r["base_eik"],
                    text_style
                )
                self.write_text(
                    eadd, row, 44,
                    r["base_name"],
                    text_style
                )

                eadd.write(
                    row, 47,
                    r["date"],
                    date_style
                )

                # Zara code / additional information
                self.write_text(
                    eadd, row, 51,
                    r["zara_code"],
                    text_style
                )

                self.write_text(
                    eadd, row, 53,
                    "СТРАНАТА",
                    text_style
                )

                eadd.write(row, 55, 0, integer_style)

                # IMPORTANT:
                # The product link code is kept as the application's
                # product relationship key. It controls which product
                # record supplies KN code, fuel type and helper values.
                #
                # We do NOT write it into an arbitrary ZaraEx import
                # column unless that column is confirmed by the source
                # format. This avoids corrupting the import structure.

                if r.get("helper_bj") is not None:
                    eadd.write(
                        row,
                        61,
                        int(r["helper_bj"]),
                        integer_style
                    )

                # Existing helper value from the current working model.
                eadd.write(row, 62, 19604, integer_style)

            workbook.save(output)
            workbook.close()
            workbook = None

            messagebox.showinfo(
                "Готово",
                "ZaraEx файлът е генериран успешно:\n\n"
                + os.path.abspath(output)
            )

        except PermissionError:
            messagebox.showerror(
                "Грешка",
                "Файлът не може да бъде записан.\n\n"
                "Ако е отворен в Excel, затвори го и опитай отново."
            )

        except Exception as exc:
            messagebox.showerror(
                "Грешка при генериране",
                str(exc)
            )

        finally:
            if workbook is not None:
                workbook.close()

    @staticmethod
    def write_text(sheet, row, col, value, style):
        sheet.write(
            row,
            col,
            "" if value is None else str(value),
            style
        )


if __name__ == "__main__":
    app = ZaraExApp()
    app.mainloop()
