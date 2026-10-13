"""ZaraEx PDF workspaces with page-shaped drop targets and real page previews."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps
import pypdfium2 as pdfium

from pdf_tools import IMAGE_EXTENSIONS, image_pages, images_to_pdf, compress_pdf
from pdf_merge import pages_from_pdf
from pdf_drop_ui import PageDropZone, ThumbnailGallery
from pdf_merge_ui import PdfMergeView

BG = "#F4F7FB"
NAVY = "#17365D"
TEXT = "#172D49"
MUTED = "#61718A"


def image_thumbnail(page):
    """Render the actual input frame used for the corresponding output PDF page."""
    with Image.open(page.source) as image:
        image.seek(page.frame)
        frame = ImageOps.exif_transpose(image.copy()).convert("RGBA")
        background = Image.new("RGBA", frame.size, "white")
        background.alpha_composite(frame)
        background.thumbnail((142, 170), Image.Resampling.LANCZOS)
        return background.convert("RGB")


def pdf_thumbnail(page):
    """Render a real PDF page, including its text and graphics, for preview only."""
    document = pdfium.PdfDocument(page.source)
    try:
        source_page = document[page.number]
        try:
            width, height = source_page.get_size()
            scale = min(142 / max(width, 1), 170 / max(height, 1))
            bitmap = source_page.render(scale=max(scale, 0.05))
            try:
                return bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()
        finally:
            source_page.close()
    finally:
        document.close()


class PdfToolsView:
    def __init__(self, parent):
        self.parent = parent
        self.images = []        # image frames, in exported page order
        self.pdf_source = None
        self.pdf_pages = []

        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True, padx=22, pady=18)
        tk.Label(container, text="PDF инструменти", bg=BG, fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(container, text="Конвертиране, компресиране и обединяване на PDF — локално на компютъра.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 16))

        self.tool_tabs = ttk.Notebook(container)
        self.tool_tabs.pack(fill="both", expand=True)
        image_tab = tk.Frame(self.tool_tabs, bg=BG)
        compress_tab = tk.Frame(self.tool_tabs, bg=BG)
        merge_tab = tk.Frame(self.tool_tabs, bg=BG)
        self.tool_tabs.add(image_tab, text="  Изображения към PDF  ")
        self.tool_tabs.add(compress_tab, text="  Компресиране на PDF  ")
        self.tool_tabs.add(merge_tab, text="  Обединяване на PDF  ")
        self._build_images(image_tab)
        self._build_compression(compress_tab)
        self.merger = PdfMergeView(merge_tab)

    def _build_images(self, parent):
        card = self._card(parent, "Изображения към PDF",
                          "Добавете снимки и ги подредете в желания ред за PDF документа.")
        self.image_drop = PageDropZone(
            card, title="Пуснете изображенията тук",
            hint="JPG · PNG · WebP · TIFF · BMP · GIF   |   или натиснете +",
            on_browse=self.add_images, on_drop=self.ingest_images)
        self.image_drop.pack(fill="x", pady=(0, 13))

        toolbar = tk.Frame(card, bg="white")
        self.image_toolbar = toolbar
        self._button(toolbar, "Добави още", self.add_images, primary=False).pack(side="left")
        self._button(toolbar, "Премахни избраната", self.remove_images, primary=False).pack(
            side="left", padx=(8, 0))
        self._button(toolbar, "Изчисти", self.clear_images, primary=False).pack(
            side="left", padx=(8, 0))
        self._button(toolbar, "↑", lambda: self.move(-1), primary=False).pack(
            side="left", padx=(18, 0))
        self._button(toolbar, "↓", lambda: self.move(1), primary=False).pack(
            side="left", padx=(6, 0))
        self.image_count = tk.StringVar(value="0 страници")
        tk.Label(toolbar, textvariable=self.image_count, bg="white", fg=NAVY,
                 font=("Segoe UI", 10, "bold")).pack(side="right")

        self.image_gallery = ThumbnailGallery(
            card, render_thumbnail=image_thumbnail, on_reorder=self._reorder_images,
            on_files_drop=self.ingest_images, on_add=self.add_images,
            add_caption="Добави още", height=275)
        actions = tk.Frame(card, bg="white")
        self.image_actions = actions
        actions.pack(fill="x", pady=(12, 0))
        tk.Label(actions, text="Качество:", bg="white", fg=TEXT).pack(side="left")
        self.image_quality = tk.IntVar(value=88)
        ttk.Combobox(actions, width=6, state="readonly", textvariable=self.image_quality,
                     values=(55, 65, 75, 85, 88, 95)).pack(side="left", padx=10)
        self._button(actions, "Създай и запази PDF", self.make_pdf).pack(side="right")
        self.image_status = tk.StringVar(value="Добавете снимки с drag-and-drop или с бутона +.")
        tk.Label(card, textvariable=self.image_status, bg="white", fg=MUTED,
                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(9, 0))

    def _build_compression(self, parent):
        card = self._card(parent, "Намаляване размера на PDF",
                          "Пуснете PDF, прегледайте страниците и изберете настройките за компресиране.")
        self.pdf_drop = PageDropZone(
            card, title="Пуснете PDF файла тук",
            hint="PDF документ   |   или натиснете +",
            on_browse=self.select_pdf, on_drop=self.ingest_pdf)
        self.pdf_drop.pack(fill="x", pady=(0, 13))

        toolbar = tk.Frame(card, bg="white")
        self.pdf_toolbar = toolbar
        self._button(toolbar, "Избери друг PDF", self.select_pdf, primary=False).pack(side="left")
        self._button(toolbar, "Премахни PDF", self.clear_pdf, primary=False).pack(
            side="left", padx=8)
        self.pdf_label = tk.StringVar(value="Няма избран PDF файл.")
        tk.Label(toolbar, textvariable=self.pdf_label, bg="white", fg=MUTED,
                 anchor="w").pack(side="left", padx=12)
        self.pdf_count = tk.StringVar(value="0 страници")
        tk.Label(toolbar, textvariable=self.pdf_count, bg="white", fg=NAVY,
                 font=("Segoe UI", 10, "bold")).pack(side="right")
        self.pdf_gallery = ThumbnailGallery(
            card, render_thumbnail=pdf_thumbnail, on_files_drop=self.ingest_pdf,
            on_add=self.select_pdf, add_caption="Избери друг PDF",
            height=275)

        options = tk.Frame(card, bg="white")
        self.pdf_options = options
        options.pack(fill="x", pady=(12, 0))
        tk.Label(options, text="Качество:", bg="white", fg=TEXT).pack(side="left")
        self.pdf_quality = tk.IntVar(value=65)
        ttk.Combobox(options, textvariable=self.pdf_quality, width=6, state="readonly",
                     values=(40, 50, 65, 75, 85, 95)).pack(side="left", padx=(8, 18))
        tk.Label(options, text="Макс. размер на изображение (px):",
                 bg="white", fg=TEXT).pack(side="left")
        self.pdf_size = tk.IntVar(value=1800)
        ttk.Combobox(options, textvariable=self.pdf_size, width=7, state="readonly",
                     values=(900, 1200, 1800, 2400, 3200)).pack(side="left", padx=8)
        self._button(options, "Компресирай и запази", self.make_compressed).pack(side="right")
        self.pdf_status = tk.StringVar(value="Оригиналният PDF се запазва непроменен.")
        tk.Label(card, textvariable=self.pdf_status, bg="white", fg=MUTED,
                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(10, 0))

    @staticmethod
    def _card(parent, title, subtitle):
        card = tk.Frame(parent, bg="white", highlightbackground="#DBE4EF",
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(card, bg="white")
        body.pack(fill="both", expand=True, padx=18, pady=13)
        tk.Label(body, text=title, bg="white", fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text=subtitle, bg="white", fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 13))
        return body

    @staticmethod
    def _button(parent, title, command, primary=True):
        color = NAVY if primary else "#EAF1FA"
        fg = "white" if primary else NAVY
        return tk.Button(parent, text=title, command=command, bg=color, fg=fg,
                         activebackground=color, activeforeground=fg,
                         relief="flat", padx=13, pady=8, cursor="hand2",
                         font=("Segoe UI", 10, "bold"))

    def _sync_image_presentation(self):
        """Only one upload surface is visible: large empty or final '+' tile."""
        if self.images:
            self.image_drop.pack_forget()
            self.image_toolbar.pack(fill="x", pady=(0, 9),
                                    before=self.image_actions)
            self.image_gallery.pack(fill="both", expand=True,
                                    before=self.image_actions)
        else:
            self.image_toolbar.pack_forget()
            self.image_gallery.pack_forget()
            self.image_drop.pack(fill="x", pady=(0, 13),
                                 before=self.image_actions)

    def _sync_pdf_presentation(self):
        if self.pdf_pages:
            self.pdf_drop.pack_forget()
            self.pdf_toolbar.pack(fill="x", pady=(0, 9),
                                  before=self.pdf_options)
            self.pdf_gallery.pack(fill="both", expand=True,
                                  before=self.pdf_options)
        else:
            self.pdf_toolbar.pack_forget()
            self.pdf_gallery.pack_forget()
            self.pdf_drop.pack(fill="x", pady=(0, 13),
                               before=self.pdf_options)

    def add_images(self):
        patterns = " ".join("*" + ext for ext in IMAGE_EXTENSIONS)
        chosen = filedialog.askopenfilenames(
            parent=self.parent, title="Добавете изображения",
            filetypes=[("Изображения", patterns), ("Всички файлове", "*.*")])
        if chosen:
            self.ingest_images(chosen)

    def ingest_images(self, paths):
        errors = []
        added = 0
        for path in paths:
            if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
                errors.append(Path(path).name + ": неподдържан формат")
                continue
            try:
                for item in image_pages([path]):
                    if item not in self.images:
                        self.images.append(item)
                        added += 1
            except (ValueError, OSError) as exc:
                errors.append(str(exc))
        if added:
            self._sync_image_presentation()
            self.image_gallery.set_items(self.images, selected=len(self.images)-1)
        self.image_count.set(f"{len(self.images)} страници")
        self.image_status.set(f"{added} нови страници · {len(self.images)} общо")
        if errors:
            messagebox.showwarning("Неуспешно добавяне", "\n".join(errors[:8]),
                                   parent=self.parent)

    def _reorder_images(self, start, target):
        if 0 <= start < len(self.images) and 0 <= target < len(self.images):
            entry = self.images.pop(start)
            self.images.insert(target, entry)
            self.image_gallery.set_items(self.images, selected=target)

    def move(self, offset):
        index = self.image_gallery.selected
        if index is not None:
            self._reorder_images(index, index + offset)

    def remove_images(self):
        index = self.image_gallery.selected
        if index is None:
            return
        self.images.pop(index)
        self.image_gallery.set_items(self.images, selected=min(index, len(self.images)-1))
        self._sync_image_presentation()
        self.image_count.set(f"{len(self.images)} страници")

    def clear_images(self):
        self.images.clear()
        self.image_gallery.clear()
        self._sync_image_presentation()
        self.image_count.set("0 страници")
        self.image_status.set("Добавете снимки с drag-and-drop или с бутона +.")

    def make_pdf(self):
        if not self.images:
            messagebox.showwarning("Изображения", "Първо добавете изображения.",
                                   parent=self.parent)
            return
        target = filedialog.asksaveasfilename(
            parent=self.parent, title="Запази PDF", defaultextension=".pdf",
            initialfile="images.pdf", filetypes=[("PDF", "*.pdf")])
        if not target:
            return
        try:
            count = images_to_pdf(self.images, target, quality=self.image_quality.get())
            self.image_status.set(f"Създаден PDF: {Path(target).name} ({count} стр.)")
            messagebox.showinfo("Готово", "PDF файлът е запазен:\n" + target,
                                parent=self.parent)
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self.parent)

    def select_pdf(self):
        chosen = filedialog.askopenfilename(
            parent=self.parent, title="Изберете PDF файл",
            filetypes=[("PDF", "*.pdf")])
        if chosen:
            self.ingest_pdf([chosen])

    def ingest_pdf(self, paths):
        if not paths:
            return
        if len(paths) != 1:
            messagebox.showwarning(
                "Само един PDF", "Компресирането обработва по един PDF файл. "
                "За обединяване на няколко файла използвайте раздела „Обединяване на PDF“.",
                parent=self.parent)
            return
        try:
            pages = pages_from_pdf(paths[0])
        except (ValueError, OSError) as exc:
            messagebox.showerror("Невалиден PDF", str(exc), parent=self.parent)
            return
        self.pdf_source = str(Path(paths[0]).expanduser().resolve())
        self.pdf_pages = pages
        self.pdf_label.set(Path(self.pdf_source).name)
        self.pdf_count.set(f"{len(pages)} страници")
        self._sync_pdf_presentation()
        self.pdf_gallery.set_items(pages)
        self.pdf_status.set("Избраният PDF ще бъде компресиран изцяло. Оригиналът остава непроменен.")

    def clear_pdf(self):
        self.pdf_source = None
        self.pdf_pages.clear()
        self.pdf_gallery.clear()
        self._sync_pdf_presentation()
        self.pdf_label.set("Няма избран PDF файл.")
        self.pdf_count.set("0 страници")
        self.pdf_status.set("Оригиналният PDF се запазва непроменен.")

    def make_compressed(self):
        if not self.pdf_source:
            messagebox.showwarning("PDF", "Първо изберете PDF файл.",
                                   parent=self.parent)
            return
        source = Path(self.pdf_source)
        target = filedialog.asksaveasfilename(
            parent=self.parent, title="Запази компресиран PDF",
            defaultextension=".pdf", initialfile=source.stem + "_compressed.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not target:
            return
        try:
            result = compress_pdf(source, target, quality=self.pdf_quality.get(),
                                  max_dimension=self.pdf_size.get())
            self.pdf_status.set(
                f"Преди: {result.original_bytes / 1024:.1f} KB | "
                f"След: {result.output_bytes / 1024:.1f} KB | "
                f"Спестени: {result.saved_percent:.1f}%")
            messagebox.showinfo("Готово", "PDF файлът е запазен:\n" + target,
                                parent=self.parent)
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self.parent)


def create_pdf_tab(parent):
    return PdfToolsView(parent)
