"""Reusable page-shaped drop target and image/PDF thumbnail gallery for Tkinter."""
from pathlib import Path
import tkinter as tk
from PIL import ImageTk

INK = "#17365D"
MUTED = "#637792"
BORDER = "#B7C9E3"
BLUE = "#2563EB"


def bind_file_drop(widget, callback, *, on_hover=None):
    """Register native Windows Explorer file drops, including paths with spaces."""
    try:
        from tkinterdnd2 import DND_FILES
        widget.drop_target_register(DND_FILES)
        def dropped(event):
            if on_hover:
                on_hover(False)
            callback(widget.tk.splitlist(event.data))
            return "copy"
        widget.dnd_bind("<<Drop>>", dropped)
        if on_hover:
            widget.dnd_bind("<<DropEnter>>", lambda event: (on_hover(True), "copy")[1])
            widget.dnd_bind("<<DropLeave>>", lambda event: (on_hover(False), "copy")[1])
        return True
    except (tk.TclError, ImportError, AttributeError):
        return False


class PageDropZone(tk.Frame):
    """Dashed drop area, with an outlined document and a centered plus icon."""

    def __init__(self, parent, *, title, hint, on_browse, on_drop):
        super().__init__(parent, bg="white")
        self.title = title
        self.hint = hint
        self.on_browse = on_browse
        self.on_drop = on_drop
        self.hovered = False
        self.canvas = tk.Canvas(self, height=212, bg="#F7FAFF", cursor="hand2",
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", self._redraw)
        self.canvas.bind("<Button-1>", lambda event: self.on_browse())
        for widget in (self, self.canvas):
            bind_file_drop(widget, self.on_drop, on_hover=self._highlight)

    def _highlight(self, active):
        self.hovered = active
        self._redraw()

    def _redraw(self, event=None):
        canvas = self.canvas
        width = max(380, canvas.winfo_width())
        height = max(206, canvas.winfo_height())
        canvas.delete("all")
        accent = BLUE if self.hovered else BORDER
        canvas.configure(bg="#EAF2FF" if self.hovered else "#F7FAFF")
        # Dashed enclosing rectangle, matching conventional upload interfaces.
        canvas.create_rectangle(10, 8, width - 10, height - 8, dash=(8, 6),
                                outline=accent, width=2, tags="drop_outline")
        cx = width / 2
        # Portrait page silhouette, with a folded corner and '+' in its center.
        left, top, right, bottom = cx - 32, 24, cx + 32, 112
        canvas.create_polygon(left, top, right - 15, top, right, top + 15,
                              right, bottom, left, bottom, left, top,
                              fill="white", outline=BLUE, width=2)
        canvas.create_line(right - 15, top, right - 15, top + 15, right, top + 15,
                           fill=BLUE, width=2)
        canvas.create_text(cx, 70, text="+", fill=BLUE,
                           font=("Segoe UI", 30, "bold"))
        canvas.create_text(cx, 142, text=self.title, fill=INK,
                           font=("Segoe UI", 12, "bold"))
        canvas.create_text(cx, 172, text=self.hint, fill=MUTED,
                           font=("Segoe UI", 10))


class ThumbnailGallery(tk.Frame):
    """Scrollable, selectable thumbnails with lazy rendering and optional reorder."""

    TILE_WIDTH = 164
    TILE_HEIGHT = 246

    def __init__(self, parent, *, render_thumbnail, on_reorder=None,
                 on_files_drop=None, on_add=None, add_caption="Добави още",
                 height=275):
        super().__init__(parent, bg="white")
        self.render_thumbnail = render_thumbnail
        self.on_reorder = on_reorder
        self.on_files_drop = on_files_drop
        self.on_add = on_add
        self.add_caption = add_caption
        self.items = []
        self.tiles = []
        self.cache = {}
        self.selected = None
        self.drag_from = None
        self.pending = []
        self.job = None
        self.generation = 0
        self.columns = 0
        self.canvas = tk.Canvas(self, bg="white", height=height, bd=0,
                                highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.inner = tk.Frame(self.canvas, bg="white")
        self.canvas.create_window((12, 12), window=self.inner, anchor="nw")
        self.add_tile = None
        self.add_canvas = None
        if self.on_add:
            self._create_add_tile()
        self.inner.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        if on_files_drop:
            for widget in (self, self.canvas, self.inner):
                bind_file_drop(widget, on_files_drop)

    def _create_add_tile(self):
        """The final, compact dashed page is an action, not an exportable page."""
        self.add_tile = tk.Frame(
            self.inner, bg="white", width=self.TILE_WIDTH,
            height=self.TILE_HEIGHT, highlightthickness=0
        )
        self.add_tile.grid_propagate(False)
        self.add_canvas = tk.Canvas(
            self.add_tile, bg="#F7FAFF", cursor="hand2",
            highlightthickness=0, bd=0, width=self.TILE_WIDTH,
            height=self.TILE_HEIGHT,
        )
        self.add_canvas.pack(fill="both", expand=True)
        self.add_canvas.bind("<Configure>", self._draw_add_tile)
        self.add_canvas.bind("<Button-1>", lambda event: self.on_add())
        if self.on_files_drop:
            for widget in (self.add_tile, self.add_canvas):
                bind_file_drop(widget, self.on_files_drop,
                               on_hover=self._highlight_add_tile)

    def _highlight_add_tile(self, hovering):
        self._draw_add_tile(hovering=hovering)

    def _draw_add_tile(self, event=None, *, hovering=False):
        canvas = self.add_canvas
        if canvas is None:
            return
        width = self.TILE_WIDTH
        height = self.TILE_HEIGHT
        accent = BLUE if hovering else BORDER
        canvas.delete("all")
        canvas.configure(bg="#EAF2FF" if hovering else "#F7FAFF")
        canvas.create_rectangle(
            6, 6, width - 7, height - 7, dash=(6, 5),
            outline=accent, width=2, tags="add_outline",
        )
        left, top, right, bottom = 51, 43, 113, 129
        canvas.create_polygon(
            left, top, right - 16, top, right, top + 16,
            right, bottom, left, bottom, fill="white",
            outline=BLUE, width=2,
        )
        canvas.create_line(
            right - 16, top, right - 16, top + 16, right, top + 16,
            fill=BLUE, width=2,
        )
        canvas.create_text(width / 2, 91, text="+",
                           font=("Segoe UI", 28, "bold"), fill=BLUE)
        canvas.create_text(
            width / 2, 165, text=self.add_caption,
            font=("Segoe UI", 11, "bold"), fill=INK,
        )
        canvas.create_text(
            width / 2, 192, text="Натисни или пусни файл",
            font=("Segoe UI", 8), fill=MUTED,
        )

    def _update_scrollregion(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _resize(self, event):
        columns = max(1, (event.width - 20) // (self.TILE_WIDTH + 12))
        if columns != self.columns:
            self.columns = columns
            self._layout()

    def clear(self):
        self.clear_tiles()
        self.cache.clear()

    def set_items(self, items, *, selected=None):
        new_items = list(items)
        # The bitmap cache survives reorder but not files being removed/replaced.
        self.cache = {key: image for key, image in self.cache.items() if key in new_items}
        self.clear_tiles()
        self.items = new_items
        self.selected = selected if selected is not None and 0 <= selected < len(new_items) else None
        for idx, item in enumerate(new_items):
            tile = tk.Frame(self.inner, width=self.TILE_WIDTH, height=self.TILE_HEIGHT,
                            bg="white", highlightbackground=BORDER, highlightthickness=2)
            tile.grid_propagate(False)
            tile.grid_columnconfigure(0, weight=1)
            tile._page_index = idx
            thumb = tk.Label(tile, text="Преглед...", bg="#F1F5FB", fg=MUTED,
                             width=19, height=11, font=("Segoe UI", 10))
            thumb.grid(row=0, column=0, padx=8, pady=(8, 7))
            caption = tk.Label(tile, text="Страница " + str(idx + 1), bg="white",
                               fg=INK, font=("Segoe UI", 10, "bold"))
            caption.grid(row=1, column=0)
            filename = Path(item.source).name
            if len(filename) > 22:
                filename = filename[:19] + "..."
            note = tk.Label(tile, text=filename, bg="white", fg=MUTED,
                            font=("Segoe UI", 9))
            note.grid(row=2, column=0, padx=4, pady=(4, 0))
            tile.preview_label = thumb
            self.tiles.append(tile)
            for widget in (tile, thumb, caption, note):
                widget.bind("<ButtonPress-1>", self._press)
                widget.bind("<ButtonRelease-1>", self._release)
                widget.bind("<MouseWheel>", self._wheel)
                if self.on_files_drop:
                    bind_file_drop(widget, self.on_files_drop)
        self._layout()
        self._paint()
        self.pending = [(self.generation, i, item) for i, item in enumerate(self.items)]
        self.job = self.after(10, self._next_preview) if self.pending else None

    def clear_tiles(self):
        if self.job is not None:
            try:
                self.after_cancel(self.job)
            except tk.TclError:
                pass
        self.job = None
        self.generation += 1
        self.pending.clear()
        self.drag_from = None
        for tile in self.tiles:
            tile.destroy()
        self.tiles = []
        self.items = []
        self.selected = None
        if self.add_tile is not None:
            self.add_tile.grid_remove()

    def _layout(self):
        columns = max(1, self.columns)
        for index, tile in enumerate(self.tiles):
            tile._page_index = index
            tile.grid(row=index // columns, column=index % columns,
                      sticky="nw", padx=(0, 12), pady=(0, 12))
        # Always append the "+" after the real page thumbnails. It must
        # never count as a selected page or be included in PDF conversion.
        if self.add_tile is not None:
            if self.items:
                index = len(self.items)
                self.add_tile.grid(row=index // columns, column=index % columns,
                                   sticky="nw", padx=(0, 12), pady=(0, 12))
            else:
                self.add_tile.grid_remove()
        self._update_scrollregion()

    def _hit(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if hasattr(widget, "_page_index"):
                return widget._page_index
            widget = getattr(widget, "master", None)
        return None

    def _press(self, event):
        self.drag_from = self._hit(event)
        self.selected = self.drag_from
        self._paint()

    def _release(self, event):
        target = self._hit(event)
        if (self.on_reorder is not None and self.drag_from is not None
                and target is not None and target != self.drag_from):
            self.on_reorder(self.drag_from, target)
        else:
            self._paint()
        self.drag_from = None

    def _paint(self):
        for idx, tile in enumerate(self.tiles):
            tile.configure(highlightbackground=BLUE if idx == self.selected else BORDER)

    def _next_preview(self):
        self.job = None
        if not self.pending or not self.winfo_exists():
            return
        generation, index, item = self.pending.pop(0)
        if generation != self.generation:
            return
        if item not in self.cache:
            try:
                self.cache[item] = ImageTk.PhotoImage(self.render_thumbnail(item))
            except Exception:
                self.cache[item] = None
        if index < len(self.tiles) and self.items[index] == item:
            photo = self.cache[item]
            label = self.tiles[index].preview_label
            if photo is None:
                label.configure(text="Няма преглед", image="")
            else:
                label.configure(image=photo, text="", width=148, height=175)
                label._photo = photo
        if self.pending:
            self.job = self.after(8, self._next_preview)
