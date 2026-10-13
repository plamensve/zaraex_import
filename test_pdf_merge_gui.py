"""GUI regression tests for the PDF merger's shared drag-and-drop preview UX."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

import tkinter as tk
from pypdf import PdfReader, PdfWriter


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"),
                     "Requires a graphical display")
class PdfMergeGuiTests(unittest.TestCase):
    def test_dropzone_becomes_inline_add_tile_and_merges_in_preview_order(self):
        from tkinterdnd2 import TkinterDnD
        from pdf_merge_ui import PdfMergeView
        from pdf_merge import merge_pdf_pages

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            first = folder / "one document.pdf"
            second = folder / "another.pdf"
            third = folder / "third document.pdf"
            for filename, dimensions in (
                (first, (210, 310)), (second, (410,)), (third, (610,))
            ):
                writer = PdfWriter()
                for width in dimensions:
                    writer.add_blank_page(width=width, height=600)
                with filename.open("wb") as stream:
                    writer.write(stream)

            root = TkinterDnD.Tk()
            root.geometry("1070x800+10+10")
            try:
                view = PdfMergeView(root)
                root.update()

                # Before import: only the large, outlined page-shaped dropzone.
                self.assertTrue(view.drop.winfo_ismapped())
                self.assertFalse(view.gallery.winfo_ismapped())
                self.assertFalse(view.toolbar.winfo_ismapped())
                self.assertTrue(view.drop.canvas.find_withtag("drop_outline"))
                self.assertTrue(view.drop.canvas.dnd_bind("<<Drop>>"))

                # Simulate Explorer paths with spaces, preserving input document order.
                payload = root.tk.call("list", str(first), str(second))
                view._on_external_drop(SimpleNamespace(data=payload))
                root.update()
                self.assertEqual(len(view.pages.pages), 3)
                self.assertEqual(len(view.gallery.tiles), 3)
                self.assertEqual(view.counter.get(), "3 страници")
                self.assertFalse(view.drop.winfo_ismapped())
                self.assertTrue(view.toolbar.winfo_ismapped())
                self.assertTrue(view.gallery.winfo_ismapped())
                self.assertTrue(view.gallery.add_tile.winfo_ismapped())
                self.assertEqual(len(view.gallery.add_canvas.find_withtag("add_outline")), 1)
                self.assertTrue(view.gallery.add_canvas.dnd_bind("<<Drop>>"))

                deadline = time.monotonic() + 7
                while time.monotonic() < deadline:
                    root.update()
                    if not view.gallery.pending and view.gallery.job is None:
                        break
                    time.sleep(0.02)
                self.assertTrue(all(tile.preview_label.cget("image")
                                    for tile in view.gallery.tiles))

                # Drag the first actual page over the third thumbnail.
                tile0, tile2 = view.gallery.tiles[0], view.gallery.tiles[2]
                from_point = SimpleNamespace(
                    x_root=tile0.winfo_rootx() + 35, y_root=tile0.winfo_rooty() + 35)
                to_point = SimpleNamespace(
                    x_root=tile2.winfo_rootx() + 35, y_root=tile2.winfo_rooty() + 35)
                view.gallery._press(from_point)
                view.gallery._release(to_point)
                self.assertEqual(
                    [(Path(p.source).name, p.number) for p in view.pages.pages],
                    [("one document.pdf", 1), ("another.pdf", 0),
                     ("one document.pdf", 0)]
                )

                # The inline '+' opens the picker and APPENDS a file's pages.
                with patch("pdf_merge_ui.filedialog.askopenfilenames",
                           return_value=(str(third),)):
                    view.gallery.add_canvas.event_generate("<Button-1>", x=45, y=80)
                root.update()
                self.assertEqual(len(view.pages.pages), 4)
                self.assertEqual(len(view.gallery.tiles), 4)
                self.assertEqual(view.pages.pages[-1].source, str(third.resolve()))
                self.assertTrue(view.gallery.add_tile.winfo_ismapped())
                self.assertFalse(view.drop.winfo_ismapped())

                output = folder / "merged.pdf"
                merge_pdf_pages(view.pages.pages, output)
                self.assertEqual(
                    [int(p.mediabox.width) for p in PdfReader(str(output)).pages],
                    [310, 410, 210, 610],
                )

                # Remove the selected newly-added page without removing the '+'.
                view.remove_selected()
                root.update()
                self.assertEqual(len(view.pages.pages), 3)
                self.assertEqual(len(view.gallery.tiles), 3)
                self.assertTrue(view.gallery.add_tile.winfo_ismapped())

                view.clear_all()
                root.update()
                self.assertEqual(view.counter.get(), "0 страници")
                self.assertEqual(len(view.gallery.tiles), 0)
                self.assertFalse(view.gallery.winfo_ismapped())
                self.assertFalse(view.gallery.add_tile.winfo_ismapped())
                self.assertTrue(view.drop.winfo_ismapped())
                self.assertTrue(view.drop.canvas.dnd_bind("<<Drop>>"))

                # Import after clearing still works via the large drop target.
                view.add_files([str(second)])
                root.update()
                self.assertEqual(len(view.pages.pages), 1)
                self.assertTrue(view.gallery.add_tile.winfo_ismapped())
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
