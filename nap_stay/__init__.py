"""E_STAY_GEN, embedded as the НАП – Декларации за престой tab."""

import tkinter as tk
from tkinter import ttk


def create_stay_tab(parent):
    """Mount a scrollable view and return the callback to save address rows."""
    background = "#F4F7FB"
    area = tk.Frame(parent, bg=background)
    area.pack(fill="both", expand=True)
    canvas = tk.Canvas(area, bg=background, highlightthickness=0, borderwidth=0)
    style = ttk.Style(parent)
    style.configure("NapStay.Vertical.TScrollbar", background="#C1D8D3",
                    troughcolor=background, arrowcolor="#087F75")
    scrollbar = ttk.Scrollbar(area, orient="vertical", command=canvas.yview,
                              style="NapStay.Vertical.TScrollbar")
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas, bg=background)
    parent.stay_content = content
    parent.stay_canvas = canvas
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

    from .eStayGen import AutocompleteEntry, mount_stay_declarations
    save_addresses = mount_stay_declarations(content)

    def descendants(widget):
        yield widget
        for child in widget.winfo_children():
            if not isinstance(child, tk.Toplevel):
                yield from descendants(child)

    def scroll(event):
        # Bind within this module only; other modules and calendar popups keep
        # their own wheel behavior. Close root-level completion overlays first.
        for widget in descendants(content):
            if isinstance(widget, AutocompleteEntry):
                widget.hide_listbox()
        if content.winfo_height() > canvas.winfo_height():
            direction = -1 if event.num == 4 or getattr(event, "delta", 0) > 0 else 1
            steps = max(1, abs(getattr(event, "delta", 0)) // 120)
            canvas.yview_scroll(direction * steps, "units")
        return "break"

    for widget in (canvas, *descendants(content)):
        widget.bind("<MouseWheel>", scroll, add="+")
        widget.bind("<Button-4>", scroll, add="+")
        widget.bind("<Button-5>", scroll, add="+")
    return save_addresses
