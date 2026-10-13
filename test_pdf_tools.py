"""Offline tests for PDF conversion, compression and file safety."""
from pathlib import Path
from tempfile import TemporaryDirectory
import random
import unittest

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from pdf_tools import images_to_pdf, compress_pdf


class PdfToolsTests(unittest.TestCase):
    def test_converts_png_and_webp_to_ordered_pages(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            one = directory / "one.png"
            two = directory / "two.webp"
            target = directory / "combined.pdf"
            Image.new("RGBA", (400, 200), (255, 0, 0, 128)).save(one)
            Image.new("RGB", (300, 600), "blue").save(two)
            self.assertEqual(images_to_pdf([one, two], target), 2)
            reader = PdfReader(str(target))
            self.assertEqual(len(reader.pages), 2)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 192)
            self.assertAlmostEqual(float(reader.pages[1].mediabox.height), 288)

    def test_image_compression_reduces_pdf_and_preserves_text(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            image = directory / "scan.png"
            picture_pdf = directory / "picture.pdf"
            source = directory / "source.pdf"
            result_file = directory / "compressed.pdf"
            data = random.Random(3).randbytes(1100 * 1100 * 3)
            Image.frombytes("RGB", (1100, 1100), data).save(image)
            with Image.open(image) as picture:
                picture.save(picture_pdf, "PDF", resolution=150, quality=95)
            writer = PdfWriter()
            writer.append(str(picture_pdf))
            page = writer.add_blank_page(width=300, height=300)
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
            font_ref = writer._add_object(font)
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
            })
            stream = DecodedStreamObject()
            stream.set_data(b"BT /F1 12 Tf 30 240 Td (Searchable invoice text) Tj ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
            with source.open("wb") as handle:
                writer.write(handle)

            result = compress_pdf(source, result_file, quality=45, max_dimension=900)
            self.assertLess(result.output_bytes, result.original_bytes)
            self.assertGreater(result.optimized_images, 0)
            reader = PdfReader(str(result_file))
            self.assertEqual(len(reader.pages), 2)
            self.assertIn("Searchable invoice text", reader.pages[1].extract_text())

    def test_no_images_copy_original_and_no_overwrite(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "plain.pdf"
            result = Path(folder) / "plain_smaller.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=400, height=400)
            with source.open("wb") as handle:
                writer.write(handle)
            stats = compress_pdf(source, result)
            self.assertEqual(stats.output_bytes, stats.original_bytes)
            self.assertEqual(result.read_bytes(), source.read_bytes())
            with self.assertRaises(ValueError):
                compress_pdf(source, source)


if __name__ == "__main__":
    unittest.main()
