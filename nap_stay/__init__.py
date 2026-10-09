"""E_STAY_GEN, embedded as the НАП – Декларации за престой tab."""

import tkinter as tk
from tkinter import ttk


def create_stay_tab(parent):
    """Mount a scrollable view and return the callback to save address rows."""
    area = ttk.Frame(parent)
    area.pack(fill="both", expand=True)
    canvas = tk.Canvas(area, highlightthickness=0, borderwidth=0)
    scrollbar = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

    from .eStayGen import mount_stay_declarations
    return mount_stay_declarations(content)
