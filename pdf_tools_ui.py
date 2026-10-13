"""Third ZaraEx workspace: image-to-PDF and PDF optimization."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pdf_tools import IMAGE_EXTENSIONS, compress_pdf, images_to_pdf

BG = "#F4F7FB"
NAVY = "#17365D"
TEXT = "#172D49"


class PdfToolsView:
    def __init__(self, parent):
        self.parent = parent
        self.images = []
        self.pdf_source = None
        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(container, text="PDF инструменти", bg=BG, fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(container, text="Конвертирайте изображения и оптимизирайте PDF файлове локално.",
                 bg=BG, fg="#61718A", font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 16))

        images_card = self._card(container, "Изображения към PDF",
                                 "Добавете изображения. Редът в списъка определя реда на страниците.")
        actions = tk.Frame(images_card, bg="white")
        actions.pack(fill="x", pady=(0, 8))
        self._button(actions, "Добави изображения", self.add_images).pack(side="left")
        self._button(actions, "Премахни", self.remove_images, primary=False).pack(side="left", padx=6)
        self._button(actions, "Нагоре", lambda: self.move(-1), primary=False).pack(side="left")
        self._button(actions, "Надолу", lambda: self.move(1), primary=False).pack(side="left", padx=6)
        self.listbox = tk.Listbox(images_card, selectmode="extended", height=5,
                                  font=("Segoe UI", 10), relief="solid", bd=1,
                                  activestyle="none", exportselection=False)
        self.listbox.pack(fill="x")
        bottom = tk.Frame(images_card, bg="white")
        bottom.pack(fill="x", pady=(12, 0))
        tk.Label(bottom, text="Качество на изображенията:", bg="white",
                 fg=TEXT).pack(side="left")
        self.image_quality = tk.IntVar(value=88)
        ttk.Combobox(bottom, width=6, state="readonly", textvariable=self.image_quality,
                     values=(55, 65, 75, 85, 88, 95)).pack(side="left", padx=10)
        self._button(bottom, "Създай и запази PDF", self.make_pdf).pack(side="right")
        self.image_status = tk.StringVar(value="Няма добавени изображения.")
        tk.Label(images_card, textvariable=self.image_status, bg="white", fg="#61718A",
                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(8, 0))

        pdf_card = self._card(container, "Намаляване размера на PDF",
                              "Компресирайте изображенията вътре в PDF, без да превръщате текста в снимка.")
        chooser = tk.Frame(pdf_card, bg="white")
        chooser.pack(fill="x")
        self._button(chooser, "Избери PDF файл", self.select_pdf).pack(side="left")
        self.pdf_label = tk.StringVar(value="Няма избран PDF файл.")
        tk.Label(chooser, textvariable=self.pdf_label, bg="white", fg=TEXT,
                 anchor="w").pack(side="left", padx=12)
        options = tk.Frame(pdf_card, bg="white")
        options.pack(fill="x", pady=(15, 0))
        tk.Label(options, text="Качество:", bg="white", fg=TEXT).pack(side="left")
        self.pdf_quality = tk.IntVar(value=65)
        ttk.Combobox(options, textvariable=self.pdf_quality, width=6, state="readonly",
                     values=(40, 50, 65, 75, 85, 95)).pack(side="left", padx=(8, 18))
        tk.Label(options, text="Макс. размер на изображение (px):", bg="white",
                 fg=TEXT).pack(side="left")
        self.pdf_size = tk.IntVar(value=1800)
        ttk.Combobox(options, textvariable=self.pdf_size, width=7, state="readonly",
                     values=(900, 1200, 1800, 2400, 3200)).pack(side="left", padx=8)
        self._button(options, "Компресирай и запази", self.make_compressed).pack(side="right")
        self.pdf_status = tk.StringVar(value="Оригиналният PDF се запазва непроменен.")
        tk.Label(pdf_card, textvariable=self.pdf_status, bg="white", fg="#61718A",
                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(10, 0))

    @staticmethod
    def _card(parent, title, subtitle):
        card = tk.Frame(parent, bg="white", highlightbackground="#DBE4EF",
                        highlightthickness=1)
        card.pack(fill="x", pady=(0, 16))
        body = tk.Frame(card, bg="white")
        body.pack(fill="x", padx=20, pady=16)
        tk.Label(body, text=title, bg="white", fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text=subtitle, bg="white", fg="#61718A",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 14))
        return body

    @staticmethod
    def _button(parent, title, command, primary=True):
        color = NAVY if primary else "#EAF1FA"
        fg = "white" if primary else NAVY
        return tk.Button(parent, text=title, command=command, bg=color, fg=fg,
                         activebackground=color, activeforeground=fg,
                         relief="flat", padx=13, pady=8, cursor="hand2",
                         font=("Segoe UI", 10, "bold"))

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for path in self.images:
            self.listbox.insert(tk.END, Path(path).name)
        self.image_status.set(str(len(self.images)) + " избрани изображения.")

    def add_images(self):
        patterns = " ".join("*" + suffix for suffix in IMAGE_EXTENSIONS)
        selected = filedialog.askopenfilenames(parent=self.parent,
                      title="Избери изображения", filetypes=[("Изображения", patterns), ("Всички файлове", "*.*")])
        for path in selected:
            if Path(path).suffix.lower() in IMAGE_EXTENSIONS and path not in self.images:
                self.images.append(path)
        self.refresh_list()

    def remove_images(self):
        for index in reversed(self.listbox.curselection()):
            self.images.pop(index)
        self.refresh_list()

    def move(self, offset):
        selected = self.listbox.curselection()
        if len(selected) != 1:
            return
        index = selected[0]
        destination = index + offset
        if not 0 <= destination < len(self.images):
            return
        self.images[index], self.images[destination] = self.images[destination], self.images[index]
        self.refresh_list()
        self.listbox.selection_set(destination)

    def make_pdf(self):
        if not self.images:
            messagebox.showwarning("Изображения", "Първо добавете изображения.", parent=self.parent)
            return
        target = filedialog.asksaveasfilename(parent=self.parent, title="Запази PDF",
                   defaultextension=".pdf", initialfile="images.pdf", filetypes=[("PDF", "*.pdf")])
        if not target:
            return
        try:
            pages = images_to_pdf(self.images, target, quality=self.image_quality.get())
            self.image_status.set("Създаден PDF: " + Path(target).name + " (" + str(pages) + " стр.)")
            messagebox.showinfo("Готово", "PDF файлът е запазен:\n" + target, parent=self.parent)
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self.parent)

    def select_pdf(self):
        path = filedialog.askopenfilename(parent=self.parent, title="Избери PDF",
                                          filetypes=[("PDF", "*.pdf")])
        if path:
            self.pdf_source = path
            self.pdf_label.set(Path(path).name)

    def make_compressed(self):
        if not self.pdf_source:
            messagebox.showwarning("PDF", "Първо изберете PDF файл.", parent=self.parent)
            return
        source = Path(self.pdf_source)
        target = filedialog.asksaveasfilename(parent=self.parent, title="Запази компресиран PDF",
                   defaultextension=".pdf", initialfile=source.stem + "_compressed.pdf",
                   filetypes=[("PDF", "*.pdf")])
        if not target:
            return
        try:
            result = compress_pdf(source, target, quality=self.pdf_quality.get(),
                                  max_dimension=self.pdf_size.get())
            self.pdf_status.set("Преди: " + format(result.original_bytes / 1024, ".1f") +
                " KB | След: " + format(result.output_bytes / 1024, ".1f") +
                " KB | Спестени: " + format(result.saved_percent, ".1f") + "%")
            messagebox.showinfo("Готово", "PDF файлът е запазен:\n" + target, parent=self.parent)
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self.parent)


def create_pdf_tab(parent):
    return PdfToolsView(parent)
