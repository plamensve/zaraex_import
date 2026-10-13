"""Regression tests for ordered page merging in the desktop PDF tools."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from pdf_merge import PdfPageCollection, PdfPage, merge_pdf_pages, pages_from_pdf


def make_pdf(path, widths):
    writer = PdfWriter()
    for i, width in enumerate(widths):
        page = writer.add_blank_page(width=width, height=500)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        text = DecodedStreamObject()
        text.set_data(f"BT /F1 14 Tf 20 400 Td (Page {width}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(text)
    with open(path, "wb") as handle:
        writer.write(handle)


class MergePdfTests(unittest.TestCase):
    def test_merge_reorders_and_removes_pages_without_rasterization(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            a, b, output = (folder / name for name in ("first.pdf", "second.pdf", "merged.pdf"))
            make_pdf(a, (301, 302))
            make_pdf(b, (501, 502))
            collection = PdfPageCollection()
            collection.add_files((a, b))
            self.assertEqual(len(collection.pages), 4)
            collection.move(3, 0)
            collection.remove([2])
            self.assertEqual(len(collection.pages), 3)
            count = merge_pdf_pages(collection.pages, output)
            self.assertEqual(count, 3)
            doc = PdfReader(str(output))
            self.assertEqual([int(page.mediabox.width) for page in doc.pages],
                             [502, 301, 501])
            self.assertEqual([page.extract_text().strip() for page in doc.pages],
                             ["Page 502", "Page 301", "Page 501"])
            self.assertEqual(len(PdfReader(str(a)).pages), 2)
            self.assertEqual(len(PdfReader(str(b)).pages), 2)

    def test_duplicate_pages_allowed_and_original_protected(self):
        with TemporaryDirectory() as temp:
            a = Path(temp) / "a.pdf"
            output = Path(temp) / "result.pdf"
            make_pdf(a, (313,))
            original = a.read_bytes()
            selection = [PdfPage(str(a), 0), PdfPage(str(a), 0)]
            with self.assertRaisesRegex(ValueError, "презапише"):
                merge_pdf_pages(selection, a)
            self.assertEqual(a.read_bytes(), original)
            merge_pdf_pages(selection, output)
            self.assertEqual(len(PdfReader(str(output)).pages), 2)

    def test_invalid_inputs_cannot_destroy_a_previous_output(self):
        with TemporaryDirectory() as temp:
            a = Path(temp) / "a.pdf"
            target = Path(temp) / "merged.pdf"
            make_pdf(a, (320,))
            target.write_bytes(b"existing output")
            with self.assertRaises(ValueError):
                merge_pdf_pages([], target)
            with self.assertRaises(ValueError):
                merge_pdf_pages([PdfPage(str(a), 8)], target)
            self.assertEqual(target.read_bytes(), b"existing output")
            with self.assertRaises(ValueError):
                pages_from_pdf(Path(temp) / "missing.pdf")

    def test_bad_or_encrypted_pdf_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            bad = folder / "invalid.pdf"
            bad.write_bytes(b"not a pdf")
            with self.assertRaises(ValueError):
                pages_from_pdf(bad)
            locked = folder / "locked.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=200)
            writer.encrypt("password")
            with locked.open("wb") as file:
                writer.write(file)
            with self.assertRaisesRegex(ValueError, "защитен"):
                pages_from_pdf(locked)


if __name__ == "__main__":
    unittest.main()
