"""Visual PDF page merger using the shared ZaraEx PDF drop/preview components.

Empty workspace -> large page-shaped drop zone.
Imported pages -> ordered thumbnails and a compact final '+' tile.
PDF content is merged with pypdf; thumbnails are visual previews only.
"""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import pypdfium2 as pdfium

from pdf_drop_ui import PageDropZone, ThumbnailGallery
from pdf_merge import PdfPageCollection, merge_pdf_pages

BG = "#F4F7FB"
NAVY = "#17365D"
TEXT = "#172D49"
MUTED = "#61718A"


def pdf_page_thumbnail(item):
    """Render a scaled preview of one original PDF page, without changing the PDF."""
    document = pdfium.PdfDocument(item.source)
    try:
        page = document[item.number]
        try:
            width, height = page.get_size()
            scale = min(142 / max(width, 1), 170 / max(height, 1))
            bitmap = page.render(scale=max(scale, 0.05))
            try:
                return bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


class PdfMergeView:
    """Join documents and rearrange individual pages in an inline tile gallery."""

    def __init__(self, parent):
        self.parent = parent
        self.pages = PdfPageCollection()
        self.counter = tk.StringVar(value="0 страници")
        self.status = tk.StringVar(value="Добавете PDF файлове чрез + или drag-and-drop.")

        self.root = tk.Frame(parent, bg=BG)
        self.root.pack(fill="both", expand=True, padx=14, pady=14)
        card = tk.Frame(self.root, bg="white", highlightbackground="#DBE4EF",
                        highlightthickness=1)
        card.pack(fill="both", expand=True)
        body = tk.Frame(card, bg="white")
        body.pack(fill="both", expand=True, padx=18, pady=13)

        tk.Label(body, text="Обединяване на PDF", bg="white", fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text="Добавете PDF файлове, подредете страниците и запазете общия документ.",
                 bg="white", fg=MUTED, font=("Segoe UI", 10)).pack(
                     anchor="w", pady=(4, 13))

        self.drop = PageDropZone(
            body, title="Пуснете PDF файловете тук",
            hint="PDF документи   |   или натиснете +",
            on_browse=self.browse_files, on_drop=self.add_files)
        self.drop.pack(fill="x", pady=(0, 13))

        self.toolbar = tk.Frame(body, bg="white")
        self._button(self.toolbar, "Добави PDF файлове", self.browse_files).pack(side="left")
        self._button(self.toolbar, "Премахни страница", self.remove_selected, False).pack(
            side="left", padx=(8, 0))
        self._button(self.toolbar, "Изчисти всички", self.clear_all, False).pack(
            side="left", padx=(8, 0))
        self._button(self.toolbar, "↑", lambda: self.move_selected(-1), False).pack(
            side="left", padx=(18, 0))
        self._button(self.toolbar, "↓", lambda: self.move_selected(1), False).pack(
            side="left", padx=(6, 0))
        tk.Label(self.toolbar, textvariable=self.counter, bg="white", fg=NAVY,
                 font=("Segoe UI", 10, "bold")).pack(side="right")

        self.gallery = ThumbnailGallery(
            body, render_thumbnail=pdf_page_thumbnail, on_reorder=self._reorder,
            on_files_drop=self.add_files, on_add=self.browse_files,
            add_caption="Добави още PDF", height=300)

        self.footer = tk.Frame(body, bg="white")
        self.footer.pack(fill="x", pady=(12, 0))
        tk.Label(self.footer, textvariable=self.status, bg="white", fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(
                     side="left", fill="x", expand=True)
        self._button(self.footer, "Обедини и запази PDF", self.save_merged).pack(
            side="right")

    @staticmethod
    def _button(host, title, callback, primary=True):
        background = NAVY if primary else "#EAF1FA"
        foreground = "white" if primary else NAVY
        return tk.Button(
            host, text=title, command=callback, bg=background, fg=foreground,
            activebackground=background, activeforeground=foreground,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            padx=13, pady=8, cursor="hand2")

    def _sync_presentation(self):
        """Only one drop surface is shown, matching image/compression workflows."""
        if self.pages.pages:
            self.drop.pack_forget()
            self.toolbar.pack(fill="x", pady=(0, 9), before=self.footer)
            self.gallery.pack(fill="both", expand=True, before=self.footer)
        else:
            self.toolbar.pack_forget()
            self.gallery.pack_forget()
            self.drop.pack(fill="x", pady=(0, 13), before=self.footer)

    def _on_external_drop(self, event):
        """Support TkDND's Tcl-list file payload, including paths with spaces."""
        self.add_files(self.parent.tk.splitlist(event.data))
        return "copy"

    def browse_files(self):
        files = filedialog.askopenfilenames(
            parent=self.parent, title="Добавете PDF файлове",
            filetypes=[("PDF файлове", "*.pdf")])
        if files:
            self.add_files(files)

    def add_files(self, paths):
        count = 0
        failures = []
        for path in paths:
            try:
                added = self.pages.add_files([path])
                count += len(added)
            except Exception as exc:
                failures.append(f"{Path(path).name}: {exc}")

        if count:
            self._sync_presentation()
            # The final '+' is not part of pages and is never exported.
            self.gallery.set_items(self.pages.pages,
                                   selected=len(self.pages.pages) - 1)
        self._update_status()
        if failures:
            messagebox.showwarning("Неуспешно добавяне", "\n".join(failures[:8]),
                                   parent=self.parent)

    def _reorder(self, origin, destination):
        if not (0 <= origin < len(self.pages.pages) and
                0 <= destination < len(self.pages.pages)):
            return
        self.pages.move(origin, destination)
        self.gallery.set_items(self.pages.pages, selected=destination)
        self._update_status()

    def move_selected(self, offset):
        if self.gallery.selected is not None:
            index = self.gallery.selected
            self._reorder(index, index + offset)

    def remove_selected(self):
        index = self.gallery.selected
        if index is None:
            return
        self.pages.remove([index])
        selected = min(index, len(self.pages.pages) - 1)
        self.gallery.set_items(self.pages.pages, selected=selected)
        self._sync_presentation()
        self._update_status()

    def clear_all(self):
        self.pages.clear()
        self.gallery.clear()
        self._sync_presentation()
        self._update_status()

    def _update_status(self):
        count = len(self.pages.pages)
        self.counter.set(f"{count} страници" if count else "0 страници")
        if count:
            sources = len({entry.source for entry in self.pages.pages})
            self.status.set(
                f"{sources} PDF файла · {count} страници · "
                "плъзнете страниците, за да ги подредите")
        else:
            self.status.set("Добавете PDF файлове чрез + или drag-and-drop.")

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
            messagebox.showerror("Грешка при обединяване", str(exc),
                                 parent=self.parent)
