"""Thumbnail-based PDF page merger for ZaraEx's desktop PDF workspace.

Files can be dropped from Explorer; thumbnails can be dragged to change order.
No input is modified, and every output page retains its original PDF content.
"""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import ImageTk
import pypdfium2 as pdfium

from pdf_merge import PdfPageCollection, merge_pdf_pages

BG = "#F4F7FB"
NAVY = "#17365D"
TEXT = "#172D49"
MUTED = "#61718A"
BORDER = "#D7E2EF"


class PdfMergeView:
    TILE_WIDTH = 166
    TILE_HEIGHT = 249

    def __init__(self, parent):
        self.parent = parent
        self.pages = PdfPageCollection()
        self.tiles = []
        self.previews = {}
        self.pending_previews = []
        self.preview_job = None
        self.selected = None
        self.drag_from = None
        self.drag_to = None
        self.status = tk.StringVar(value="Добавете PDF файлове или ги пуснете тук от Explorer.")

        self.root = tk.Frame(parent, bg=BG)
        self.root.pack(fill="both", expand=True, padx=20, pady=16)
        toolbar = tk.Frame(self.root, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        self._button(toolbar, "Добави PDF файлове", self.browse_files).pack(side="left")
        self._button(toolbar, "Премахни страница", self.remove_selected, False).pack(
            side="left", padx=(8, 0))
        self._button(toolbar, "Изчисти всички", self.clear_all, False).pack(
            side="left", padx=(8, 0))
        self._button(toolbar, "↑", lambda: self.move_selected(-1), False).pack(
            side="left", padx=(18, 0))
        self._button(toolbar, "↓", lambda: self.move_selected(1), False).pack(
            side="left", padx=(6, 0))

        info = tk.Frame(self.root, bg=BG)
        info.pack(fill="x", pady=(0, 10))
        tk.Label(info, text="Плъзнете миниатюра върху друга, за да промените реда.",
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(side="left")
        self.counter = tk.StringVar(value="0 страници")
        tk.Label(info, textvariable=self.counter, font=("Segoe UI", 10, "bold"),
                 bg=BG, fg=NAVY).pack(side="right")

        gallery = tk.Frame(self.root, bg="white", highlightbackground=BORDER,
                           highlightthickness=1)
        gallery.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(gallery, bg="white", bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(gallery, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.gallery = tk.Frame(self.canvas, bg="white")
        self.gallery_window = self.canvas.create_window((12, 12), window=self.gallery, anchor="nw")
        self.gallery.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.gallery.bind("<MouseWheel>", self._on_wheel)

        self.empty = tk.Label(self.gallery, text="Пуснете PDF файлове тук\nили използвайте „Добави PDF файлове“",
                              justify="center", bg="white", fg=MUTED, padx=30,
                              pady=70, font=("Segoe UI", 12))
        self.empty.grid(row=0, column=0, sticky="w")
        self._enable_file_drop(self.root, self.canvas, self.gallery, self.empty)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", pady=(12, 0))
        tk.Label(footer, textvariable=self.status, bg=BG, fg=MUTED,
                 anchor="w", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)
        self._button(footer, "Обедини и запази PDF", self.save_merged).pack(side="right")

    @staticmethod
    def _button(host, text, command, primary=True):
        background = NAVY if primary else "#E7EFF9"
        foreground = "white" if primary else NAVY
        return tk.Button(host, text=text, command=command, bg=background, fg=foreground,
                         activebackground=background, activeforeground=foreground,
                         font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                         padx=12, pady=8, cursor="hand2")

    def _enable_file_drop(self, *widgets):
        try:
            from tkinterdnd2 import DND_FILES
            for widget in widgets:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_external_drop)
        except (ImportError, tk.TclError, AttributeError):
            self.status.set("Използвайте „Добави PDF файлове“, за да заредите документи.")

    def _on_external_drop(self, event):
        # TkinterDnD uses a Tcl list; this correctly handles paths with spaces.
        self.add_files(self.parent.tk.splitlist(event.data))
        return "copy"

    def browse_files(self):
        sources = filedialog.askopenfilenames(
            parent=self.parent, title="Изберете PDF файлове",
            filetypes=[("PDF файлове", "*.pdf")])
        if sources:
            self.add_files(sources)

    def add_files(self, paths):
        total_added = 0
        failed = []
        for path in paths:
            try:
                entries = self.pages.add_files([path])
                total_added += len(entries)
                self.pending_previews.extend(entries)
                for entry in entries:
                    self.tiles.append(self._tile(entry))
            except Exception as exc:
                failed.append(f"{Path(path).name}: {exc}")
        self._reflow()
        self._update_status()
        if total_added and self.preview_job is None:
            self.preview_job = self.root.after(15, self._render_next_preview)
        if failed:
            messagebox.showwarning("Неподдържани файлове",
                                   "\n".join(failed[:8]), parent=self.parent)

    def _tile(self, entry):
        tile = tk.Frame(self.gallery, bg="white", width=self.TILE_WIDTH,
                        height=self.TILE_HEIGHT, highlightthickness=2,
                        highlightbackground=BORDER)
        tile.grid_propagate(False)
        tile.grid_columnconfigure(0, weight=1)
        tile._merge_page_index = len(self.tiles)
        thumb = tk.Label(tile, bg="#EDF2F8", text="Зареждане...", fg=MUTED,
                         font=("Segoe UI", 10), width=19, height=11,
                         compound="center", relief="flat")
        thumb.grid(row=0, column=0, padx=8, pady=(9, 7), sticky="ew")
        caption = tk.Label(tile, text="Страница " + str(entry.number + 1),
                           bg="white", fg=TEXT, font=("Segoe UI", 10, "bold"))
        caption.grid(row=1, column=0)
        filename = Path(entry.source).name
        label = tk.Label(tile, text=filename if len(filename) < 21 else filename[:18] + "…",
                         bg="white", fg=MUTED, font=("Segoe UI", 9))
        label.grid(row=2, column=0, padx=4, pady=(3, 0), sticky="ew")
        tile._thumbnail_label = thumb
        tile._caption = caption
        for widget in (tile, thumb, caption, label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._finish_drag)
            widget.bind("<MouseWheel>", self._on_wheel)
        self._enable_file_drop(tile, thumb, caption, label)
        return tile

    def _tile_at_pointer(self, event):
        widget = self.parent.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if hasattr(widget, "_merge_page_index"):
                return widget._merge_page_index
            widget = getattr(widget, "master", None)
        return None

    def _start_drag(self, event):
        idx = self._tile_at_pointer(event)
        if idx is None:
            return
        self.drag_from = idx
        self.drag_to = idx
        self.selected = idx
        self._paint_selection()

    def _drag(self, event):
        if self.drag_from is None:
            return
        hovered = self._tile_at_pointer(event)
        if hovered is not None and hovered != self.drag_to:
            self.drag_to = hovered
            self._paint_selection()

    def _finish_drag(self, event):
        if self.drag_from is None:
            return
        destination = self._tile_at_pointer(event)
        if destination is not None and destination != self.drag_from:
            self._reorder(self.drag_from, destination)
        self.drag_from = None
        self.drag_to = None
        self._paint_selection()

    def _paint_selection(self):
        for i, tile in enumerate(self.tiles):
            border = "#2563EB" if i == self.selected else BORDER
            if i == self.drag_to and self.drag_from is not None and i != self.drag_from:
                border = "#18A589"
            tile.configure(highlightbackground=border)

    def _reorder(self, start, destination):
        self.pages.move(start, destination)
        tile = self.tiles.pop(start)
        self.tiles.insert(destination, tile)
        self.selected = destination
        self._reflow()
        self._update_status()

    def move_selected(self, offset):
        if self.selected is None:
            return
        next_position = self.selected + offset
        if 0 <= next_position < len(self.tiles):
            self._reorder(self.selected, next_position)

    def remove_selected(self):
        if self.selected is None:
            return
        index = self.selected
        self.pages.remove([index])
        tile = self.tiles.pop(index)
        tile.destroy()
        self.selected = min(index, len(self.tiles) - 1) if self.tiles else None
        self._reflow()
        self._update_status()

    def clear_all(self):
        for tile in self.tiles:
            tile.destroy()
        self.pages.clear()
        self.tiles.clear()
        self.pending_previews.clear()
        self.selected = None
        self.drag_to = None
        self.drag_from = None
        self._reflow()
        self._update_status()

    def _reflow(self):
        self.empty.grid_remove()
        for index, tile in enumerate(self.tiles):
            tile._merge_page_index = index
            tile.grid_forget()
        if not self.tiles:
            self.empty.grid()
        width = max(self.canvas.winfo_width(), 500)
        columns = max(1, (width - 22) // (self.TILE_WIDTH + 12))
        for index, tile in enumerate(self.tiles):
            tile.grid(row=index // columns, column=index % columns, sticky="nw",
                      padx=(0, 12), pady=(0, 13))
        self._paint_selection()
        self.gallery.update_idletasks()
        self._update_scrollregion()

    def _resize(self, event):
        self._reflow()

    def _update_scrollregion(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _render_next_preview(self):
        self.preview_job = None
        if not self.pending_previews or not self.root.winfo_exists():
            return
        entry = self.pending_previews.pop(0)
        key = (entry.source, entry.number)
        if key not in self.previews:
            try:
                document = pdfium.PdfDocument(entry.source)
                try:
                    page = document[entry.number]
                    try:
                        width, height = page.get_size()
                        scale = min(136 / width, 167 / height)
                        bitmap = page.render(scale=max(scale, .05))
                        try:
                            picture = bitmap.to_pil().copy()
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                finally:
                    document.close()
                self.previews[key] = ImageTk.PhotoImage(picture)
            except Exception:
                self.previews[key] = None
        photo = self.previews[key]
        for idx, item in enumerate(self.pages.pages):
            if item == entry and idx < len(self.tiles):
                label = self.tiles[idx]._thumbnail_label
                if photo is None:
                    label.configure(text="Без преглед", image="")
                else:
                    label.configure(image=photo, text="", width=148, height=177)
        if self.pending_previews:
            self.preview_job = self.root.after(5, self._render_next_preview)

    def _update_status(self):
        count = len(self.pages.pages)
        self.counter.set(f"{count} стр." if count else "0 страници")
        if count:
            count_files = len({page.source for page in self.pages.pages})
            self.status.set(f"{count_files} PDF файла · {count} страници · влачете страниците за подреждане")
        else:
            self.status.set("Добавете PDF файлове или ги пуснете тук от Explorer.")

    def save_merged(self):
        if not self.pages.pages:
            messagebox.showwarning("Липсват страници", "Първо добавете PDF страници.",
                                   parent=self.parent)
            return
        target = filedialog.asksaveasfilename(
            parent=self.parent, title="Запази обединения PDF",
            defaultextension=".pdf", initialfile="merged.pdf",
            filetypes=[("PDF файлове", "*.pdf")])
        if not target:
            return
        try:
            total = merge_pdf_pages(self.pages.pages, target)
            self.status.set(f"Запазени {total} страници: {Path(target).name}")
            messagebox.showinfo("Готово", f"Обединени са {total} страници:\n{target}",
                                parent=self.parent)
        except Exception as exc:
            messagebox.showerror("Грешка при обединяване", str(exc), parent=self.parent)
