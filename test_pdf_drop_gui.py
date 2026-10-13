"""Graphical regression tests for PDF image and compression drop targets."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter, PdfReader


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"),
                     "Requires a Tk display")
class PdfDropGuiTests(unittest.TestCase):
    def test_drop_zones_thumbnails_reordering_and_pdf_compression_preview(self):
        from tkinterdnd2 import TkinterDnD
        from pdf_tools_ui import PdfToolsView

        with TemporaryDirectory() as folder:
            root_path = Path(folder)
            first = root_path / "scan one.png"
            second = root_path / "scan two.webp"
            frames = root_path / "animation.gif"
            pdf = root_path / "multi page.pdf"
            Image.new("RGB", (360, 480), "#3399BB").save(first)
            Image.new("RGB", (440, 240), "#BB7733").save(second)
            Image.new("RGB", (200, 300), "red").save(
                frames, save_all=True, append_images=[Image.new("RGB", (200, 300), "blue")],
                duration=500)
            writer = PdfWriter()
            writer.add_blank_page(width=320, height=480)
            writer.add_blank_page(width=420, height=480)
            with pdf.open("wb") as fh:
                writer.write(fh)

            root = TkinterDnD.Tk()
            root.geometry("1280x1000+10+10")
            try:
                parent = tk.Frame(root)
                parent.pack(fill="both", expand=True)
                view = PdfToolsView(parent)
                root.update()
                for target in (view.image_drop.canvas, view.pdf_drop.canvas):
                    self.assertGreater(len(target.find_withtag("drop_outline")), 0)
                    self.assertTrue(target.dnd_bind("<<Drop>>"))

                # The Tcl list parser handles names with spaces from Explorer.
                payload = root.tk.call("list", str(first), str(second), str(frames))
                view.ingest_images(root.tk.splitlist(payload))
                root.update()
                self.assertEqual(len(view.images), 4)  # 2 images + 2 GIF frames
                self.assertEqual(len(view.image_gallery.tiles), 4)
                self._wait_for_images(root, view.image_gallery)
                self.assertTrue(all(tile.preview_label.cget("image")
                                    for tile in view.image_gallery.tiles))

                original_last = view.images[-1]
                view._reorder_images(3, 0)
                self.assertEqual(view.images[0], original_last)
                self.assertEqual(view.image_gallery.selected, 0)
                self._wait_for_images(root, view.image_gallery)
                output = root_path / "converted.pdf"
                from pdf_tools import images_to_pdf
                images_to_pdf(view.images, output)
                self.assertEqual(len(PdfReader(str(output)).pages), 4)

                # Input errors must leave the selected source and previews intact.
                view.tool_tabs.select(1)
                root.update()
                view.ingest_pdf([str(pdf)])
                root.update()
                self.assertEqual(len(view.pdf_pages), 2)
                self._wait_for_images(root, view.pdf_gallery)
                self.assertTrue(all(tile.preview_label.cget("image")
                                    for tile in view.pdf_gallery.tiles))
                old = view.pdf_source
                with patch("pdf_tools_ui.messagebox.showwarning"):
                    view.ingest_pdf([str(pdf), str(output)])
                self.assertEqual(view.pdf_source, old)
                self.assertEqual(len(view.pdf_gallery.tiles), 2)
                view.clear_pdf()
                self.assertIsNone(view.pdf_source)
                self.assertEqual(len(view.pdf_gallery.tiles), 0)
                view.clear_images()
                self.assertEqual(view.images, [])
            finally:
                root.destroy()

    @staticmethod
    def _wait_for_images(root, gallery):
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            root.update()
            if not gallery.pending and gallery.job is None:
                break
            time.sleep(0.02)


if __name__ == "__main__":
    unittest.main()
