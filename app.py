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
APP_VERSION = "1.0.0"
APP_AUTHOR = "Plamen Svetoslavov"
COPYRIGHT_NOTICE = f"© 2026 {APP_AUTHOR}. Всички права запазени."
APP_VERSION_LABEL = f"Версия {APP_VERSION}"
DATA_FILE = "zaraex_data.json"
APP_ICON_FILE = "ZaraExImport.ico"

# Main form: (field key, label, widget type, row, first column, column span).
# Each of the three input rows covers the same twelve-column grid.
# Labels are placed ABOVE the widgets in every cell for consistent alignment.
LOADING_FORM_COLUMNS = 12
LOADING_FORM_FIELDS = (
    ("date", "Дата", "entry", 0, 0, 2),
    ("ukn", "УКН", "entry", 0, 2, 3),
    ("add", "ADD №", "entry", 0, 5, 2),
    ("quantity", "Количество (л.)", "entry", 0, 7, 3),
    ("zara", "Код ЗАРА", "entry", 0, 10, 2),
    ("product", "Продукт", "combo", 1, 0, 6),
    ("base", "Петролна база", "combo", 1, 6, 3),
    ("company", "Транспортна фирма", "combo", 1, 9, 3),
    ("vehicle", "МПС", "combo", 2, 0, 3),
    ("driver", "Шофьор", "combo", 2, 3, 3),
    ("handover_name", "Име на предал горивото", "entry", 2, 6, 3),
    ("handover_egn", "ЕГН на предал горивото", "entry", 2, 9, 3),
)


def app_icon_path():
    """Locate the icon in both source checkouts and PyInstaller bundles."""
    resource_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(resource_dir, APP_ICON_FILE)


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

        # Match the title-bar/taskbar icon to the executable icon on Windows.
        if os.name == "nt":
            icon_file = app_icon_path()
            if os.path.isfile(icon_file):
                try:
                    self.iconbitmap(default=icon_file)
                except tk.TclError:
                    pass

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
        # Matching vertical padding for text inputs and readonly selectors.
        style.configure("Loading.TEntry", padding=(7, 6))
        style.configure("Loading.TCombobox", padding=(7, 6))
        style.configure("Loading.TLabel", font=("Segoe UI", 10))

    # ========================================================
    # MAIN UI
    # ========================================================

    def build_ui(self):
        header = tk.Frame(self, bg="#17365D", height=68)
        header.pack(fill="x")

        tk.Label(
            header,
            text="ZaraEx Generator",
            bg="#17365D",
            fg="white",
            font=("Segoe UI", 20, "bold")
        ).pack(side="left", padx=24, pady=17)

        self.home_button = tk.Button(
            header, text="Начало", command=self.show_home,
            font=("Segoe UI", 10, "bold"), bg="#284B75", fg="white",
            activebackground="#365F8D", activeforeground="white",
            relief="flat", borderwidth=0, padx=18, pady=9, cursor="hand2",
        )
        self.home_button.pack(side="right", padx=24)
        self.workspace_title = tk.StringVar(value="Работно пространство")
        tk.Label(
            header, textvariable=self.workspace_title, bg="#17365D",
            fg="#C8D8EC", font=("Segoe UI", 10),
        ).pack(side="right", padx=8)

        # Pack before the expanding notebook to keep authorship visible
        # at the very bottom of the window in every application tab.
        self.build_footer()

        self.workspace = tk.Frame(self, bg="#F4F7FB")
        self.workspace.pack(fill="both", expand=True)
        self.home_page = tk.Frame(self.workspace, bg="#F4F7FB")
        self.notebook = ttk.Notebook(self.workspace)

        self.main_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.stay_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="ZaraEx – Товарения")
        self.notebook.add(self.settings_tab, text="ZaraEx – Настройки")
        self.notebook.add(self.stay_tab, text="НАП – Декларации за престой")

        self.build_main_tab()
        self.build_settings_tab()

        from nap_stay import create_stay_tab
        self.save_stay_addresses = create_stay_tab(self.stay_tab)
        self.build_home_page()
        self.show_home()
        self.protocol("WM_DELETE_WINDOW", self.close_application)

    def show_home(self):
        """Return to the launcher without rebuilding either module's widgets."""
        self.notebook.pack_forget()
        self.home_page.pack(fill="both", expand=True)
        self.workspace_title.set("Работно пространство")
        self.home_button.configure(state="disabled", disabledforeground="#AFC4DF")
        self.module_buttons["import"].focus_set()

    def open_workspace(self, module):
        """Display only the selected module, retaining all pending form data."""
        modules = {
            "import": (self.main_tab, self.settings_tab),
            "stay": (self.stay_tab,),
        }
        visible_tabs = modules[module]
        self.home_page.pack_forget()
        for tab in (self.main_tab, self.settings_tab, self.stay_tab):
            self.notebook.tab(tab, state="normal" if tab in visible_tabs else "hidden")
        self.notebook.select(visible_tabs[0])
        self.notebook.pack(fill="both", expand=True, padx=14, pady=14)
        self.workspace_title.set(
            "Импортен файл" if module == "import" else "НАП – Декларации за престой"
        )
        self.home_button.configure(state="normal")
        self.notebook.focus_set()

    def build_home_page(self):
        """SaaS-style module launcher built entirely with standard Tk widgets."""
        background = "#F4F7FB"
        content = tk.Frame(self.home_page, bg=background)
        content.pack(fill="both", expand=True, padx=44, pady=(28, 20))

        hero = tk.Frame(content, bg="#132E50")
        hero.pack(fill="x")
        tk.Label(
            hero, text="ЕДНО ПРИЛОЖЕНИЕ · ДВА РАБОТНИ ПРОЦЕСА",
            bg="#132E50", fg="#94B9EB", font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=28, pady=(22, 8))
        tk.Label(
            hero, text="Документите започват оттук.",
            bg="#132E50", fg="white", font=("Segoe UI", 26, "bold"),
        ).pack(anchor="w", padx=28)
        tk.Label(
            hero, text="Изберете какво искате да подготвите. Всичко необходимо е на едно място.",
            bg="#132E50", fg="#C7D7EA", font=("Segoe UI", 11),
        ).pack(anchor="w", padx=28, pady=(10, 24))

        heading = tk.Frame(content, bg=background)
        heading.pack(fill="x", pady=(24, 14))
        tk.Label(
            heading, text="Вашето работно пространство", bg=background,
            fg="#172D49", font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        tk.Label(
            heading, text="Изберете модул, за да продължите", bg=background,
            fg="#61718A", font=("Segoe UI", 10),
        ).pack(side="right")

        cards = tk.Frame(content, bg=background)
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1, uniform="module")
        cards.columnconfigure(1, weight=1, uniform="module")
        cards.rowconfigure(0, weight=1)
        self.module_buttons = {}
        self.build_module_card(
            cards, column=0, module="import", badge="XLS", accent="#2563EB",
            tint="#EAF1FF", title="Импортен файл за ZaraEx",
            description="Подгответе товаренията и генерирайте\nExcel файл за импорт в ZaraEx.",
            features="Товарения и чернови\nПродукти, фирми, МПС и петролни бази",
            action="Отвори генератора  →",
        )
        self.build_module_card(
            cards, column=1, module="stay", badge="XML", accent="#087F75",
            tint="#E5F5F1", title="НАП – Декларации за престой",
            description="Заредете ЕДП XML и подгответе\nдекларация за престой за НАП.",
            features="Област, община и населено място\nЗапазени адреси и XML декларации",
            action="Отвори декларациите  →",
        )
        tk.Label(
            content, text="Можете да сменяте модула от „Начало“, без да губите въведените данни.",
            bg=background, fg="#61718A", font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(16, 0))

    def build_module_card(self, parent, *, column, module, badge, accent, tint,
                          title, description, features, action):
        card = tk.Frame(
            parent, bg="white", highlightbackground="#DBE4EF", highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="nsew",
                  padx=(0, 10) if column == 0 else (10, 0))
        tk.Frame(card, bg=accent, height=4).pack(fill="x")
        body = tk.Frame(card, bg="white")
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(
            body, text=badge, bg=tint, fg=accent, padx=12, pady=6,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        title_label = tk.Label(
            body, text=title, bg="white", fg="#172D49", anchor="w",
            justify="left", font=("Segoe UI", 17, "bold"),
        )
        title_label.pack(fill="x", pady=(14, 8))
        description_label = tk.Label(
            body, text=description, bg="white", fg="#53657E", anchor="w",
            justify="left", font=("Segoe UI", 11),
        )
        description_label.pack(fill="x")
        button = tk.Button(
            body, text=action, command=lambda: self.open_workspace(module),
            bg=accent, fg="white", activebackground=accent, activeforeground="white",
            font=("Segoe UI", 11, "bold"), relief="flat", borderwidth=0,
            padx=18, pady=11, cursor="hand2", anchor="w",
        )
        button.pack(side="bottom", fill="x", pady=(16, 0))
        self.module_buttons[module] = button
        tk.Label(
            body, text=features, bg="white", fg="#61718A", anchor="w",
            justify="left", font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(14, 0))
        def resize_card(event):
            for label in (title_label, description_label):
                label.configure(wraplength=max(200, event.width))

        body.bind("<Configure>", resize_card)

    def close_application(self):
        """Save both modules' data before closing the shared main window."""
        if hasattr(self, "save_stay_addresses"):
            self.save_stay_addresses()
        self.destroy()

    def build_footer(self):
        """Professional bottom status bar with a concise copyright notice."""
        background = "#f4f7fb"
        footer = tk.Frame(self, bg=background)
        footer.pack(side="bottom", fill="x")

        ttk.Separator(footer, orient="horizontal").pack(fill="x")
        content = tk.Frame(footer, bg=background)
        content.pack(fill="x")

        tk.Label(
            content,
            text=COPYRIGHT_NOTICE,
            font=("Segoe UI", 9),
            bg=background,
            fg="#415672",
            anchor="w",
            padx=20,
            pady=9,
        ).pack(side="left")

        tk.Label(
            content,
            text=APP_VERSION_LABEL,
            font=("Segoe UI", 9),
            bg=background,
            fg="#607089",
            anchor="e",
            padx=20,
            pady=9,
        ).pack(side="right")

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
        self.handover_name_var = tk.StringVar()
        self.handover_egn_var = tk.StringVar()

        # One twelve-column grid for all fields. Each field has the same
        # label-above-input layout, regardless of whether it is an Entry or
        # Combobox; column spans control widths without shifting baselines.
        for column in range(LOADING_FORM_COLUMNS):
            form.columnconfigure(column, weight=1, uniform="loading")

        for key, label, kind, row, column, span in LOADING_FORM_FIELDS:
            field_frame = ttk.Frame(form)
            field_frame.grid(
                row=row, column=column, columnspan=span,
                sticky="ew", padx=6, pady=(4, 8)
            )
            field_frame.columnconfigure(0, weight=1)

            ttk.Label(
                field_frame, text=label, style="Loading.TLabel"
            ).grid(row=0, column=0, sticky="w", pady=(0, 5))

            variable = getattr(self, f"{key}_var")
            if kind == "combo":
                widget = ttk.Combobox(
                    field_frame, textvariable=variable, state="readonly",
                    style="Loading.TCombobox", width=1
                )
                setattr(self, f"{key}_combo", widget)
            else:
                widget = ttk.Entry(
                    field_frame, textvariable=variable,
                    style="Loading.TEntry", width=1
                )
            widget.grid(row=1, column=0, sticky="ew")

        self.company_combo.bind(
            "<<ComboboxSelected>>", self.on_company_changed
        )
        self.product_combo.bind(
            "<<ComboboxSelected>>", lambda event: self.update_selection_info()
        )
        self.base_combo.bind(
            "<<ComboboxSelected>>", lambda event: self.update_selection_info()
        )

        # Controls sit in their own row and do not affect the input heights.
        actions = ttk.Frame(form)
        actions.grid(
            row=3, column=0, columnspan=LOADING_FORM_COLUMNS,
            sticky="ew", padx=6, pady=(3, 9)
        )
        self.record_save_button = ttk.Button(
            actions, text="Добави товарене", style="Primary.TButton",
            command=self.add_record
        )
        self.record_save_button.pack(side="right")
        ttk.Button(
            actions, text="Използвай шофьора",
            command=self.use_driver_as_handover
        ).pack(side="right", padx=(0, 10))

        ttk.Separator(form, orient="horizontal").grid(
            row=4, column=0, columnspan=LOADING_FORM_COLUMNS,
            sticky="ew", padx=6, pady=(0, 8)
        )
        self.selection_info_var = tk.StringVar()
        # The full catalogue name can be long; wrap instead of clipping it.
        info_label = ttk.Label(
            form, textvariable=self.selection_info_var, wraplength=1050,
            justify="left"
        )
        info_label.grid(
            row=5, column=0, columnspan=LOADING_FORM_COLUMNS,
            sticky="ew", padx=6, pady=(0, 2)
        )
        form.bind(
            "<Configure>",
            lambda event: info_label.configure(
                wraplength=max(360, event.width - 40)
            ),
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
            "handover",
            "zara",
            "edit_action",
            "delete_action",
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
            "handover": "Предал горивото",
            "zara": "Код ЗАРА",
            "edit_action": "Редакция",
            "delete_action": "Премахване",
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
            "handover": 210,
            "zara": 120,
            "edit_action": 100,
            "delete_action": 100,
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

        def record_action_click(event):
            row = self.records_tree.identify_row(event.y)
            column = self.records_tree.identify_column(event.x)
            if not row:
                return
            self.records_tree.selection_set(row)
            if column == f"#{columns.index('edit_action') + 1}":
                self.edit_selected_record()
                return "break"
            if column == f"#{columns.index('delete_action') + 1}":
                self.delete_selected_records()
                return "break"

        self.records_tree.bind("<ButtonRelease-1>", record_action_click)
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
        """Show the full selected product name, CN code and loading base."""
        product = self.get_product_by_name(self.product_var.get())
        base = self.get_base_by_name(self.base_var.get())

        fuel_name = product.get("name") if product else None
        kn_code = product.get("kn_code") if product else None
        base_name = base.get("name") if base else None

        self.selection_info_var.set(
            f"Вид гориво: {fuel_name or '-'}"
            f"   |   Код по КН: {kn_code or '-'}"
            f"   |   База на товарене: {base_name or '-'}"
        )

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

    def use_driver_as_handover(self):
        """Copy the selected driver's details only when explicitly requested."""
        company = self.get_company_by_name(self.company_var.get())
        driver = self.get_driver_by_name_and_company(
            self.driver_var.get(), company.get("eik", "") if company else ""
        )
        if not driver:
            messagebox.showwarning("Липсва шофьор", "Първо избери шофьор.")
            return
        self.handover_name_var.set(driver["name"])
        self.handover_egn_var.set(driver["egn"])

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

        handover_name = self.handover_name_var.get().strip()
        handover_egn = self.handover_egn_var.get().strip()
        if not handover_name or not handover_egn:
            messagebox.showerror(
                "Липсват данни за предал горивото",
                "Попълни име и ЕГН на човека, предал горивото, "
                "или натисни „Използвай шофьора“."
            )
            return
        if len(handover_egn) != 10 or not handover_egn.isascii() or not handover_egn.isdigit():
            messagebox.showerror(
                "Невалидно ЕГН",
                "ЕГН на предалия горивото трябва да съдържа точно 10 цифри."
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
            "handover_name": handover_name,
            "handover_egn": handover_egn,

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
        self.handover_name_var.set("")
        self.handover_egn_var.set("")

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
                    r.get("handover_name") or r["driver_name"],
                    r["zara_code"],
                    "✎ Редакция",
                    "✕ Премахни",
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

                # J–O: loading location of the selected petroleum base.
                # Use the same validated administrative codes as AE–AJ.
                address = validate_address(r["base_address"])
                self.write_text(eadd, row, 9, address["region"], text_style)
                self.write_text(eadd, row, 10, address["region_code"], text_style)
                self.write_text(eadd, row, 11, address["municipality"], text_style)
                self.write_text(eadd, row, 12, address["municipality_code"], text_style)
                self.write_text(eadd, row, 13, address["city"], text_style)
                self.write_text(eadd, row, 14, address["city_code"], text_style)

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

                # Y–Z: person accepting fuel (driver).
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
                # AA–AB: actual person handing over fuel. Older saved drafts
                # without dedicated handover fields retain the driver fallback.
                self.write_text(
                    eadd, row, 26,
                    r.get("handover_name") or r["driver_name"],
                    text_style
                )
                self.write_text(
                    eadd, row, 27,
                    r.get("handover_egn") or r["driver_egn"],
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
                # AS: the issuer's EIK, not the petroleum base name.
                # ZaraEx accepts at most 14 characters in this column.
                issuer_eik = str(r.get("base_eik") or "").strip()[:14]
                self.write_text(
                    eadd, row, 44,
                    issuer_eik,
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
