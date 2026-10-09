import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import openpyxl
# pip install tkcalendar
from tkcalendar import DateEntry
import sys  # <-- добави този ред, ако още не съществува
import json
import shutil
if __package__:
    from .location_selector import LocationSelector, validate_location_codes
else:
    from location_selector import LocationSelector, validate_location_codes


def resource_path(relative_path):
    """Намира пътя до файл при работа с PyInstaller и при обикновен скрипт."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, "nap_stay", relative_path)


selected_file = None  # Глобална променлива за избрания входен файл
output_file_path = None  # Глобална променлива за избрания изходен файл


# --- Зареждане на данни от xlsx файловете ---
def load_dict_from_xlsx(filepath):
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active
    result = {}
    for row in ws.iter_rows(min_row=1, max_col=2):
        if row[1].value and isinstance(row[1].value, str):
            key = row[1].value.strip()
            code = str(row[0].value).strip() if row[0].value is not None else ''
            result[key] = code
    return result


DOMAIN_DICT = load_dict_from_xlsx(resource_path('data/domain.xlsx'))
MUNICIPALITY_DICT = load_dict_from_xlsx(resource_path('data/municipality.xlsx'))
CITY_DICT = load_dict_from_xlsx(resource_path('data/city.xlsx'))

DOMAIN_LIST = list(DOMAIN_DICT.keys())
MUNICIPALITY_LIST = list(MUNICIPALITY_DICT.keys())
CITY_LIST = list(CITY_DICT.keys())


# --- AutocompleteEntry widget ---
class AutocompleteEntry(tk.Entry):
    def __init__(self, autocomplete_list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autocomplete_list = sorted(autocomplete_list, key=str.lower)
        self.on_change_callback = None
        self.var = self["textvariable"] = tk.StringVar()
        self.var.trace('w', self.changed)
        self.bind("<Down>", self.move_down)
        self.bind("<Up>", self.move_up)
        self.bind("<Return>", self.selection)
        self.bind("<FocusOut>", lambda e: self.hide_listbox())
        self.listbox = None
        self.lb_index = 0
        self.root = self.winfo_toplevel()
        self.on_select_callback = None

    def set_on_select(self, callback):
        self.on_select_callback = callback

    def changed(self, *args):
        if self.on_change_callback:
            self.on_change_callback()
        if self.var.get() == '':
            self.hide_listbox()
            if self.on_select_callback and not self.on_change_callback:
                self.on_select_callback('')
        else:
            words = self.comparison()
            if words:
                self.show_listbox()
                self.listbox.delete(0, tk.END)
                for w in words:
                    self.listbox.insert(tk.END, w)
                self.lb_index = 0
                self.listbox.select_set(self.lb_index)
                self.listbox.activate(self.lb_index)
            else:
                self.hide_listbox()

    def selection(self, event):
        if self.listbox and self.listbox.size() > 0:
            if event is not None and event.widget is self.listbox and event.type == tk.EventType.ButtonPress:
                index = self.listbox.nearest(event.y)
            else:
                selected = self.listbox.curselection()
                index = selected[0] if selected else self.lb_index
            value = self.listbox.get(index)
            self.var.set(value)
            self.icursor(tk.END)
            self.hide_listbox()
            if self.on_select_callback:
                self.on_select_callback(value)
        return 'break'

    def move_down(self, event):
        if self.listbox:
            if self.lb_index < self.listbox.size() - 1:
                self.lb_index += 1
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(self.lb_index)
                self.listbox.activate(self.lb_index)
        return 'break'

    def move_up(self, event):
        if self.listbox:
            if self.lb_index > 0:
                self.lb_index -= 1
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(self.lb_index)
                self.listbox.activate(self.lb_index)
        return 'break'

    def show_listbox(self):
        if not self.listbox:
            self.listbox = tk.Listbox(
                self.root, font=self.cget("font"), height=7, bg="white", fg="#172D49",
                selectbackground="#087F75", selectforeground="white",
                relief="flat", borderwidth=0, highlightthickness=1,
                highlightbackground="#DBE4EF", activestyle="none", exportselection=False,
            )
            x = self.winfo_rootx() - self.root.winfo_rootx()
            y = self.winfo_rooty() - self.root.winfo_rooty() + self.winfo_height()
            self.listbox.place(x=x, y=y, width=max(240, self.winfo_width()))
            self.listbox.bind("<Button-1>", self.selection)
            self.listbox.bind("<Return>", self.selection)
        else:
            x = self.winfo_rootx() - self.root.winfo_rootx()
            y = self.winfo_rooty() - self.root.winfo_rooty() + self.winfo_height()
            self.listbox.place(x=x, y=y, width=max(240, self.winfo_width()))
            self.listbox.lift()

    def hide_listbox(self):
        if self.listbox:
            self.listbox.destroy()
            self.listbox = None

    def comparison(self):
        pattern = self.var.get().lower()
        return [w for w in self.autocomplete_list if pattern in w.lower()]


def convert_xml(input_file, output_path):
    tree = ET.parse(input_file)
    root = tree.getroot()

    try:
        ukn_eADD = root.findtext('declarationReference/ukn_eADD', '')
        date = date_entry.get()
        fuelAmount = root.findtext('fuel/fuelAmount', '')
        fuelKNCode = root.findtext('fuel/fuelKNCode', '')

        storage_type = root.findtext('transport/storage/type', 'other_no_ESFP')
        transporter_eik = root.findtext('transport/transporter/bgCompany/eik', '')

        # === Превозни средства ===
        tugcistern_elements = root.findall('transport/transportation/tugcistern')
        tugcisterns = [el.text for el in tugcistern_elements if el.text]

        tug_value = root.findtext('transport/transportation/tug', '').strip()
        registration_numbers = tugcisterns if tugcisterns else ([tug_value] if tug_value else [])

        if not registration_numbers:
            raise ValueError("Не е подаден нито един регистрационен номер!")

        # Данни за шофьора и доставчика
        receiver = root.find('receiverPerson/bgPerson')
        receiver_egn = receiver.findtext('egn', '') if receiver is not None else ''
        receiver_fname = receiver.findtext('firstName', '') if receiver is not None else ''
        receiver_lname = receiver.findtext('lastName', '') if receiver is not None else ''

        # Данни от GUI
        domain = region_code_var.get()
        municipality = municipality_code_var.get()
        city = city_code_var.get()
        address = address_entry.get().strip() if address_entry.get() != "Адрес" else ""
        address_number = number_entry.get().strip() if number_entry.get() != "№" else ""

        if not all([ukn_eADD, date, fuelAmount, fuelKNCode, domain, municipality, city, address, address_number]):
            raise ValueError("Липсват задължителни данни за генериране на XML!")
        validate_location_codes(domain, municipality, city)

        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        ET.register_namespace('xsi', nsmap['xsi'])

        stay_root = ET.Element("stayTransportDeclaration", {
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation": "baseDeclarationSchema_v1.3.xsd"
        })

        decl_ref = ET.SubElement(stay_root, "declarationReference")
        ET.SubElement(decl_ref, "ukn_eADD").text = ukn_eADD
        ET.SubElement(decl_ref, "date").text = date

        fuel = ET.SubElement(stay_root, "fuel")
        ET.SubElement(fuel, "fuelAmount").text = fuelAmount
        ET.SubElement(fuel, "fuelKNCode").text = fuelKNCode

        transport = ET.SubElement(stay_root, "transport")

        location = ET.SubElement(transport, "location")
        ET.SubElement(location, "domain").text = domain
        ET.SubElement(location, "municipality").text = municipality
        ET.SubElement(location, "city").text = city

        storage = ET.SubElement(transport, "storage")
        ET.SubElement(storage, "type").text = storage_type
        ET.SubElement(storage, "address").text = address
        ET.SubElement(storage, "addressNumber").text = address_number

        transporter = ET.SubElement(transport, "transporter")
        bgCompany = ET.SubElement(transporter, "bgCompany")
        ET.SubElement(bgCompany, "eik").text = transporter_eik

        # === Превоз ===
        transportation = ET.SubElement(transport, "transportation", {
            "{http://www.w3.org/2001/XMLSchema-instance}type": "AutoTransportationType"
        })

        # Добавяне на tugcistern елементи (ако има)
        for reg in tugcisterns:
            ET.SubElement(transportation, "tugcistern").text = reg

        # Ако няма tugcistern, използваме tug
        if not tugcisterns and tug_value:
            ET.SubElement(transportation, "tug").text = tug_value

        # Шофьор
        drivers = ET.SubElement(transportation, "drivers")
        driver_bg = ET.SubElement(drivers, "bgPerson")
        ET.SubElement(driver_bg, "egn").text = receiver_egn
        ET.SubElement(driver_bg, "firstName").text = receiver_fname
        ET.SubElement(driver_bg, "lastName").text = receiver_lname

        # Лице по доставка
        deliver_person = ET.SubElement(stay_root, "deliverPerson")
        deliver_bg = ET.SubElement(deliver_person, "bgPerson")
        ET.SubElement(deliver_bg, "egn").text = receiver_egn
        ET.SubElement(deliver_bg, "firstName").text = receiver_fname
        ET.SubElement(deliver_bg, "lastName").text = receiver_lname

        # Получател
        receiver_person = ET.SubElement(stay_root, "receiverPerson")
        receiver_bg = ET.SubElement(receiver_person, "bgPerson")
        ET.SubElement(receiver_bg, "egn").text = receiver_egn
        ET.SubElement(receiver_bg, "firstName").text = receiver_fname
        ET.SubElement(receiver_bg, "lastName").text = receiver_lname

        # Запис
        rough_string = ET.tostring(stay_root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)

        return output_path

    except Exception as e:
        raise ValueError(f"Грешка при обработката на XML: {e}")


# === Интерфейсни функции ===
def browse_file():
    global selected_file
    file_path = filedialog.askopenfilename(filetypes=[("XML файлове", "*.xml")])
    if file_path:
        selected_file = file_path
        file_label.config(text=f"Избран файл:\n{os.path.basename(file_path)}")


def choose_save_location():
    global output_file_path
    file_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML файлове", "*.xml")])
    if file_path:
        output_file_path = file_path
        save_label.config(text=f"Изходен файл:\n{os.path.basename(file_path)}")


def generate_output():
    if not selected_file:
        messagebox.showwarning("Липсва файл", "Моля, първо изберете XML файл.")
        return
    if not output_file_path:
        messagebox.showwarning("Липсва място за запис", "Моля, изберете къде да се запази изходният XML файл.")
        return
    if not region_code_var.get() or not municipality_code_var.get() or not city_code_var.get():
        messagebox.showwarning("Липсва код", "Моля, изберете валидна област, община и населено място.")
        return
    if address_entry.get() == "" or address_entry.get() == "Адрес":
        messagebox.showwarning("Липсва адрес", "Моля, въведете адрес.")
        return
    if number_entry.get() == "" or number_entry.get() == "№":
        messagebox.showwarning("Липсва номер", "Моля, въведете номер.")
        return
    try:
        output = convert_xml(selected_file, output_file_path)
        messagebox.showinfo("Успех", f"Файлът е създаден:\n{output}")
        clear_fields()
    except Exception as e:
        messagebox.showerror("Грешка", str(e))


# Функция за изчистване на всички полета
def clear_fields():
    # Дата (reset до днешна дата)
    try:
        date_entry.set_date('today')
    except Exception:
        pass
    # Адрес
    address_entry.delete(0, tk.END)
    address_entry.insert(0, "   Адрес")
    address_entry.config(fg="gray")
    # Номер
    number_entry.delete(0, tk.END)
    number_entry.insert(0, "   №")
    number_entry.config(fg="gray")
    # Autocomplete полета и кодове
    region_entry.delete(0, tk.END)
    region_entry.insert(0, "   Област")
    region_entry.config(fg="gray")
    region_code_var.set("")
    municipality_entry.delete(0, tk.END)
    municipality_entry.insert(0, "   Община")
    municipality_entry.config(fg="gray")
    municipality_code_var.set("")
    city_entry.delete(0, tk.END)
    city_entry.insert(0, "   Населено място")
    city_entry.config(fg="gray")
    city_code_var.set("")
    # File labels
    file_label.config(text="Няма избран файл")
    save_label.config(text="")



def saved_addresses_path():
    """Use persistent local storage, copying any old working-directory data."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    folder = os.path.join(base, "ZaraExImport", "nap_stay")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, "saved_addresses.json")
    legacy = os.path.join(os.getcwd(), "saved_addresses.json")
    if not os.path.isfile(target) and os.path.isfile(legacy):
        shutil.copyfile(legacy, target)
    return target


def mount_stay_declarations(parent):
    """Mount the styled NRA workspace while retaining the original XML workflow."""
    global date_entry, region_entry, municipality_entry, city_entry
    global region_code_var, municipality_code_var, city_code_var
    global address_entry, number_entry, file_label, save_label
    global selected_file, output_file_path
    selected_file = None
    output_file_path = None
    root = parent
    background = "#F4F7FB"
    text_color = "#172D49"
    muted = "#61718A"
    accent = "#087F75"
    border = "#DBE4EF"
    root.configure(bg=background)
    page = tk.Frame(root, bg=background)
    page.pack(fill="both", expand=True, padx=24, pady=20)

    def label(host, text, *, color=text_color, size=10, bold=False, bg="white"):
        return tk.Label(host, text=text, bg=bg, fg=color, anchor="w",
                        justify="left", font=("Segoe UI", size, "bold" if bold else "normal"))

    def button(host, text, command, *, primary=False, danger=False):
        normal = accent if primary else ("#FFF0F0" if danger else "#EAF4F2")
        foreground = "white" if primary else ("#B33D45" if danger else accent)
        hover = "#06675F" if primary else ("#FFE1E3" if danger else "#D8EDE8")
        widget = tk.Button(host, text=text, command=command, bg=normal, fg=foreground,
                           activebackground=hover, activeforeground=foreground,
                           font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0,
                           padx=14, pady=9, cursor="hand2", highlightthickness=1,
                           highlightbackground=normal, highlightcolor=accent)
        widget.bind("<Enter>", lambda event: widget.configure(bg=hover))
        widget.bind("<Leave>", lambda event: widget.configure(bg=normal))
        return widget

    def section(title, subtitle):
        card = tk.Frame(page, bg="white", highlightbackground=border, highlightthickness=1)
        card.pack(fill="x", pady=(0, 14))
        body = tk.Frame(card, bg="white")
        body.pack(fill="x", padx=20, pady=16)
        label(body, title, size=13, bold=True).pack(anchor="w")
        label(body, subtitle, color=muted).pack(anchor="w", pady=(4, 12))
        return body

    def input_options():
        return dict(font=("Segoe UI", 11), width=1, relief="flat", borderwidth=0,
                    bg="#F8FAFD", fg=text_color, insertbackground=accent,
                    highlightthickness=1, highlightbackground=border, highlightcolor=accent)

    def placeholder(entry, text):
        entry.insert(0, text)
        entry.configure(fg=muted)
        def clear(event):
            if entry.get().strip() in (text, ""):
                entry.delete(0, tk.END)
                entry.configure(fg=text_color)
        def restore(event):
            if not entry.get().strip():
                entry.insert(0, text)
                entry.configure(fg=muted)
        entry.bind("<FocusIn>", clear, add="+")
        entry.bind("<FocusOut>", restore, add="+")

    def location_field(host, column, title, values, catalogue, *, value=None, code=""):
        cell = tk.Frame(host, bg="white")
        cell.grid(row=0, column=column, sticky="ew", padx=(0, 12) if column < 2 else 0)
        heading = tk.Frame(cell, bg="white")
        heading.pack(fill="x", pady=(0, 5))
        label(heading, title, bold=True).pack(side="left")
        label(heading, "Код", color=muted, size=9).pack(side="right", padx=12)
        inputs = tk.Frame(cell, bg="white")
        inputs.pack(fill="x")
        inputs.columnconfigure(0, weight=1)
        entry = AutocompleteEntry(values, inputs, **input_options())
        entry.grid(row=0, column=0, sticky="ew", ipady=7)
        variable = tk.StringVar(value=code)
        code_entry = tk.Entry(inputs, textvariable=variable, state="readonly", width=7,
                              justify="center", font=("Segoe UI", 10), fg=accent,
                              readonlybackground="#EAF4F2", relief="flat", borderwidth=0)
        code_entry.grid(row=0, column=1, sticky="ns", padx=(6, 0), ipady=7)
        entry.set_on_select(lambda selected: variable.set(catalogue.get(selected, "")))
        if value and value.strip() != title:
            entry.insert(0, value)
        else:
            placeholder(entry, title)
        entry.hide_listbox()
        return entry, variable, code_entry

    def plain_field(host, column, title, hint, *, value=None, span=1):
        cell = tk.Frame(host, bg="white")
        cell.grid(row=0, column=column, columnspan=span, sticky="ew", padx=(0, 12) if column < 2 else 0)
        label(cell, title, bold=True).pack(anchor="w", pady=(0, 5))
        entry = tk.Entry(cell, **input_options())
        entry.pack(fill="x", ipady=7)
        if value and value.strip() != hint:
            entry.insert(0, value)
        else:
            placeholder(entry, hint)
        return entry

    hero = tk.Frame(page, bg="#133B40")
    hero.pack(fill="x", pady=(0, 16))
    label(hero, "НАП – Декларации за престой", bg="#133B40", color="white",
          size=20, bold=True).pack(anchor="w", padx=22, pady=(12, 6))
    label(hero, "От входен ЕДП файл до готова XML декларация — в няколко стъпки.",
          bg="#133B40", color="#C2DFDA", size=11).pack(anchor="w", padx=22, pady=(0, 12))

    files = tk.Frame(page, bg=background)
    files.pack(fill="x", pady=(0, 14))
    for column in range(2):
        files.columnconfigure(column, weight=1, uniform="files")
    file_labels = []
    for column, title, hint, action, command in (
            (0, "1. Входен файл", "Изберете ЕДП XML", "Избери входен файл ЕДП", browse_file),
            (1, "2. Изходен файл", "Изберете къде да запишете декларацията", "Избери място за запис", choose_save_location)):
        card = tk.Frame(files, bg="white", highlightbackground=border, highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 7) if column == 0 else (7, 0))
        body = tk.Frame(card, bg="white")
        body.pack(fill="both", expand=True, padx=18, pady=14)
        toolbar = tk.Frame(body, bg="white")
        toolbar.pack(fill="x")
        label(toolbar, title, size=12, bold=True).pack(side="left")
        button(toolbar, action, command).pack(side="right")
        file_status = label(body, hint, color=muted)
        file_status.pack(fill="x", pady=(8, 0))
        body.bind("<Configure>", lambda event, widget=file_status:
                  widget.configure(wraplength=max(120, event.width)))
        file_labels.append(file_status)
    file_label, save_label = file_labels

    location = section("3. Място и дата на престой",
                       "Въведете име и изберете от предложенията. Административните кодове се попълват автоматично.")
    places = tk.Frame(location, bg="white")
    places.pack(fill="x")
    for column in range(3):
        places.columnconfigure(column, weight=1, uniform="location")
    region_entry, region_code_var, _ = location_field(places, 0, "Област", DOMAIN_LIST, DOMAIN_DICT)
    municipality_entry, municipality_code_var, _ = location_field(places, 1, "Община", MUNICIPALITY_LIST, MUNICIPALITY_DICT)
    city_entry, city_code_var, _ = location_field(places, 2, "Населено място", CITY_LIST, CITY_DICT)
    root.location_selector = LocationSelector(
        {"region": region_entry, "municipality": municipality_entry, "city": city_entry},
        {"region": region_code_var, "municipality": municipality_code_var, "city": city_code_var},
    )

    address_row = tk.Frame(location, bg="white")
    address_row.pack(fill="x", pady=(14, 0))
    address_row.columnconfigure(0, weight=2, uniform="address")
    address_row.columnconfigure(1, weight=5, uniform="address")
    address_row.columnconfigure(2, weight=1, uniform="address")
    date_cell = tk.Frame(address_row, bg="white")
    date_cell.grid(row=0, column=0, sticky="ew", padx=(0, 12))
    label(date_cell, "Дата на престой", bold=True).pack(anchor="w", pady=(0, 5))
    date_entry = DateEntry(date_cell, font=("Segoe UI", 11), width=1,
                           date_pattern="dd.mm.yyyy", style="NapStay.DateEntry",
                           background=accent, foreground="white", borderwidth=0,
                           headersbackground="#EAF4F2", headersforeground=text_color,
                           selectbackground=accent, selectforeground="white")
    date_entry.pack(fill="x", ipady=6)
    address_entry = plain_field(address_row, 1, "Улица / местност", "Адрес")
    number_entry = plain_field(address_row, 2, "Номер", "№")

    actions = tk.Frame(page, bg="#E5F5F1", highlightbackground="#CBE5DE", highlightthickness=1)
    actions.pack(fill="x", pady=(0, 22))
    button(actions, "Генерирай XML", generate_output, primary=True).pack(side="right", padx=16, pady=12)
    label(actions, "Подгответе декларацията", bg="#E5F5F1", color=accent,
          size=11, bold=True).pack(side="left", padx=18)

    SAVED_ADDRESSES_PATH = saved_addresses_path()


    # --- Функции за зареждане и запис на адреси ---
    def load_saved_addresses():
        try:
            with open(SAVED_ADDRESSES_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                return [{} for _ in range(5)]
            return [(item if isinstance(item, dict) else {}) for item in (data + [{} for _ in range(5)])[:5]]
        except (OSError, ValueError, TypeError):
            return [{} for _ in range(5)]


    def save_addresses(addresses):
        with open(SAVED_ADDRESSES_PATH, 'w', encoding='utf-8') as f:
            json.dump(addresses, f, ensure_ascii=False, indent=2)



    saved_section = section("Запазени адреси", "Пет адресни шаблона за повторна употреба. Промените се запазват автоматично.")
    transport_frame = tk.Frame(saved_section, bg="white")
    transport_frame.pack(fill="x")
    transport_entries = []
    root.saved_address_rows = transport_entries
    saved_addresses = load_saved_addresses()
    region_entry_main = region_entry
    region_code_var_main = region_code_var
    municipality_entry_main = municipality_entry
    municipality_code_var_main = municipality_code_var
    city_entry_main = city_entry
    city_code_var_main = city_code_var

    for i in range(5):
        row = {}
        card = tk.Frame(transport_frame, bg="white", highlightbackground=border, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        row_frame = tk.Frame(card, bg="white")
        row_frame.pack(fill="x", padx=14, pady=12)
        label(row_frame, f"{i + 1:02d}", color=accent, bold=True, size=12).pack(side="left", padx=(0, 12))
        company_cell = tk.Frame(row_frame, bg="white")
        company_cell.pack(side="left", fill="x", expand=True, padx=(0, 16))
        label(company_cell, "Транспортна фирма", color=muted, size=9).pack(anchor="w", pady=(0, 3))
        row['company'] = tk.Entry(company_cell, **input_options())
        row['company'].pack(fill="x", ipady=5)
        if saved_addresses[i].get('company') and saved_addresses[i]['company'] != f"Тр. Фирма {i + 1}":
            row['company'].insert(0, saved_addresses[i]['company'])
        else:
            placeholder(row['company'], f"Тр. Фирма {i + 1}")
        row_actions = tk.Frame(row_frame, bg="white")
        row_actions.pack(side="right")
        details = tk.Frame(card, bg="white")
        fields = tk.Frame(details, bg="white")
        fields.pack(fill="x", pady=(0, 12))
        for column in range(3):
            fields.columnconfigure(column, weight=1, uniform="saved_location")
        for column, key, title, values, catalogue in (
                (0, 'region', 'Област', DOMAIN_LIST, DOMAIN_DICT),
                (1, 'municipality', 'Община', MUNICIPALITY_LIST, MUNICIPALITY_DICT),
                (2, 'city', 'Населено място', CITY_LIST, CITY_DICT)):
            row[key], row[key + '_code_var'], row[key + '_code'] = location_field(
                fields, column, title, values, catalogue,
                value=saved_addresses[i].get(key), code=saved_addresses[i].get(key + '_code', ''))
        row['location_selector'] = LocationSelector(
            {key: row[key] for key in ("region", "municipality", "city")},
            {key: row[key + '_code_var'] for key in ("region", "municipality", "city")},
        )
        address_fields = tk.Frame(details, bg="white")
        address_fields.pack(fill="x")
        for column, weight in enumerate((1, 4, 1)):
            address_fields.columnconfigure(column, weight=weight, uniform="saved_address")
        row['address'] = plain_field(address_fields, 0, "Улица / местност", f"Адрес {i + 1}",
                                     value=saved_addresses[i].get('address'), span=2)
        row['number'] = plain_field(address_fields, 2, "Номер", f"№{i + 1}", value=saved_addresses[i].get('number'))

        def apply_address(
                region_entry=row['region'], region_code_var=row['region_code_var'],
                municipality_entry=row['municipality'], municipality_code_var=row['municipality_code_var'],
                city_entry=row['city'], city_code_var=row['city_code_var'],
                addr_entry=row['address'], num_entry=row['number']):

            # Apply to main fields for XML
            region_entry_val = region_entry.get()
            municipality_entry_val = municipality_entry.get()
            city_entry_val = city_entry.get()
            address_val = addr_entry.get()
            number_val = num_entry.get()

            # Main region
            region_entry_main.delete(0, tk.END)
            region_entry_main.insert(0, region_entry_val)
            region_entry_main.config(fg="black")
            region_code_var_main.set(region_code_var.get())
            if hasattr(region_entry_main, 'on_select_callback') and region_entry_main.on_select_callback:
                region_entry_main.on_select_callback(region_entry_val)

            # Main municipality
            municipality_entry_main.delete(0, tk.END)
            municipality_entry_main.insert(0, municipality_entry_val)
            municipality_entry_main.config(fg="black")
            municipality_code_var_main.set(municipality_code_var.get())
            if hasattr(municipality_entry_main, 'on_select_callback') and municipality_entry_main.on_select_callback:
                municipality_entry_main.on_select_callback(municipality_entry_val)

            # Main city
            city_entry_main.delete(0, tk.END)
            city_entry_main.insert(0, city_entry_val)
            city_entry_main.config(fg="black")
            city_code_var_main.set(city_code_var.get())
            if hasattr(city_entry_main, 'on_select_callback') and city_entry_main.on_select_callback:
                city_entry_main.on_select_callback(city_entry_val)

            # Main address
            address_entry.delete(0, tk.END)
            address_entry.insert(0, address_val)
            address_entry.config(fg="black")

            # Main number
            number_entry.delete(0, tk.END)
            number_entry.insert(0, number_val)
            number_entry.config(fg="black")


        def clear_row(idx=i):
            for key, entry in transport_entries[idx].items():
                if isinstance(entry, tk.Entry):
                    if key == 'company':
                        entry.delete(0, tk.END)
                        entry.insert(0, f"Тр. Фирма {idx + 1}")
                        entry.config(fg="gray")
                    elif key == 'address':
                        entry.delete(0, tk.END)
                        entry.insert(0, f"Адрес {idx + 1}")
                        entry.config(fg="gray")
                    elif key == 'number':
                        entry.delete(0, tk.END)
                        entry.insert(0, f"№{idx + 1}")
                        entry.config(fg="gray")
                    elif key == 'region':
                        entry.delete(0, tk.END)
                        entry.insert(0, "Област")
                        entry.config(fg="gray")
                    elif key == 'municipality':
                        entry.delete(0, tk.END)
                        entry.insert(0, "Община")
                        entry.config(fg="gray")
                    elif key == 'city':
                        entry.delete(0, tk.END)
                        entry.insert(0, "Населено място")
                        entry.config(fg="gray")
                elif isinstance(entry, tk.StringVar):
                    entry.set("")
            # Изтриване от файла
            saved_addresses[idx] = {}
            save_addresses(saved_addresses)



        def toggle_details(frame=details, widgets=row):
            if frame.winfo_manager():
                frame.pack_forget()
                widgets['toggle_button'].configure(text="Редактирай")
            else:
                frame.pack(fill="x", padx=14, pady=(0, 16))
                widgets['toggle_button'].configure(text="Скрий полетата")
        def apply_saved_address(callback=apply_address):
            callback()
            for entry in (region_entry_main, municipality_entry_main, city_entry_main):
                entry.hide_listbox()
            if isinstance(root.master, tk.Canvas):
                root.master.yview_moveto(0)
            date_entry.focus_set()

        button(row_actions, "Приложи адрес", apply_saved_address, primary=True).pack(side="left", padx=(0, 8))
        row['toggle_button'] = button(row_actions, "Редактирай", toggle_details)
        row['toggle_button'].pack(side="left", padx=(0, 8))
        button(row_actions, "Изтрий адрес", clear_row, danger=True).pack(side="left")

        # --- Автоматично запазване при промяна ---
        def save_row(event=None, idx=i, row=row):
            if row is None:
                row = row
            saved_addresses[idx] = {
                'region': row['region'].get(),
                'region_code': row['region_code_var'].get(),
                'municipality': row['municipality'].get(),
                'municipality_code': row['municipality_code_var'].get(),
                'city': row['city'].get(),
                'city_code': row['city_code_var'].get(),
                'company': row['company'].get(),
                'address': row['address'].get(),
                'number': row['number'].get().strip(),
            }
            save_addresses(saved_addresses)


        for key in ['region', 'municipality', 'city', 'company', 'address', 'number']:
            row[key].bind('<FocusOut>', save_row, add='+')

        transport_entries.append(row)

    def on_close():
        for idx, row in enumerate(transport_entries):
            saved_addresses[idx] = {
                'region': row['region'].get(),
                'region_code': row['region_code_var'].get(),
                'municipality': row['municipality'].get(),
                'municipality_code': row['municipality_code_var'].get(),
                'city': row['city'].get(),
                'city_code': row['city_code_var'].get(),
                'company': row['company'].get(),
                'address': row['address'].get(),
                'number': row['number'].get().strip(),
            }
        save_addresses(saved_addresses)




    return on_close


if __name__ == "__main__":
    window = tk.Tk()
    window.title("НАП – Декларации за престой")
    window.geometry("1350x850")
    close_stay = mount_stay_declarations(window)

    def close_window():
        close_stay()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close_window)
    window.mainloop()
