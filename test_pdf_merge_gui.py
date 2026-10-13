"""Tkinter PDF merger smoke tests; run with xvfb-run on Linux."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import tkinter as tk
import unittest

from pypdf import PdfReader, PdfWriter


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"),
                     "Requires a graphical display")
class PdfMergeGuiTests(unittest.TestCase):
    def test_thumbnail_grid_drop_import_drag_reorder_and_export(self):
        from tkinterdnd2 import TkinterDnD
        from pdf_merge_ui import PdfMergeView
        from pdf_merge import merge_pdf_pages

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            first, second = folder / "one document.pdf", folder / "another.pdf"
            for filename, dimensions in ((first, [210, 310]), (second, [410])):
                writer = PdfWriter()
                for width in dimensions:
                    writer.add_blank_page(width=width, height=600)
                with filename.open("wb") as stream:
                    writer.write(stream)

            root = TkinterDnD.Tk()
            root.geometry("970x740+10+10")
            try:
                view = PdfMergeView(root)
                root.update()
                # A file dropped from Explorer can contain spaces in its path.
                payload = root.tk.call("list", str(first), str(second))
                view._on_external_drop(SimpleNamespace(data=payload))
                root.update()
                self.assertEqual(len(view.pages.pages), 3)
                self.assertEqual(len(view.tiles), 3)
                for tile in view.tiles:
                    self.assertIsInstance(tile._thumbnail_label, tk.Label)
                for _ in range(40):
                    root.update()
                    if not view.pending_previews and view.preview_job is None:
                        break
                self.assertTrue(all(tile._thumbnail_label.cget("image") for tile in view.tiles))
                tile0, tile2 = view.tiles[0], view.tiles[2]
                origin = SimpleNamespace(
                    x_root=tile0.winfo_rootx()+40, y_root=tile0.winfo_rooty()+40)
                destination = SimpleNamespace(
                    x_root=tile2.winfo_rootx()+40, y_root=tile2.winfo_rooty()+40)
                view._start_drag(origin)
                view._drag(destination)
                view._finish_drag(destination)
                self.assertEqual([(Path(p.source).name, p.number) for p in view.pages.pages],
                                 [("one document.pdf", 1), ("another.pdf", 0),
                                  ("one document.pdf", 0)])
                output = folder / "merged.pdf"
                merge_pdf_pages(view.pages.pages, output)
                self.assertEqual([int(p.mediabox.width) for p in PdfReader(output).pages],
                                 [310, 410, 210])
                view.remove_selected()
                self.assertEqual(len(view.pages.pages), 2)
                view.clear_all()
                self.assertEqual(view.counter.get(), "0 страници")
                self.assertEqual(len(view.tiles), 0)
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
