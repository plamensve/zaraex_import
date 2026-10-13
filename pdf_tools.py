"""Offline image/PDF operations using permissively licensed Pillow and pypdf."""
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import os
import shutil
import tempfile

from PIL import Image, ImageOps, ImageSequence
from pypdf import PdfReader, PdfWriter

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff")


@dataclass(frozen=True)
class CompressionResult:
    original_bytes: int
    output_bytes: int
    optimized_images: int

    @property
    def saved_percent(self):
        return 100 * (self.original_bytes - self.output_bytes) / max(1, self.original_bytes)


def _rgb(image):
    image = ImageOps.exif_transpose(image)
    if "A" in image.getbands() or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def images_to_pdf(paths, output_path, *, dpi=150, quality=88):
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("Изберете поне едно изображение.")
    if not 30 <= dpi <= 600 or not 25 <= quality <= 95:
        raise ValueError("Невалидни настройки.")
    if any(not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS for p in paths):
        raise ValueError("Неподдържан формат или липсващо изображение.")
    if any(os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(output_path)) for p in paths):
        raise ValueError("Изходният файл трябва да е различен от входния.")
    frames = []
    for path in paths:
        try:
            with Image.open(path) as image:
                for frame in ImageSequence.Iterator(image):
                    frames.append(_rgb(frame.copy()))
        except OSError as exc:
            raise ValueError("Неуспешно отваряне: " + path.name) from exc
    frames[0].save(str(output_path), "PDF", save_all=True,
                   append_images=frames[1:], resolution=dpi, quality=quality)
    return len(frames)


def compress_pdf(source_path, output_path, *, quality=65, max_dimension=1800):
    source, output = Path(source_path), Path(output_path)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("Изберете валиден PDF файл.")
    if os.path.normcase(os.path.abspath(source)) == os.path.normcase(os.path.abspath(output)):
        raise ValueError("Изходният файл трябва да е различен от оригинала.")
    if not 25 <= quality <= 95 or not 400 <= max_dimension <= 5000:
        raise ValueError("Невалидни настройки.")
    reader = PdfReader(str(source))
    if reader.is_encrypted:
        raise ValueError("PDF файлът е защитен с парола.")
    original = source.stat().st_size
    writer = PdfWriter()
    writer.append(reader)
    optimized = 0
    handled = set()
    for page in writer.pages:
        for item in page.images:
            ref = item.indirect_reference
            if ref is None or ref.idnum in handled:
                continue
            handled.add(ref.idnum)
            try:
                image = item.image
                if "A" in image.getbands() or "transparency" in image.info:
                    continue
                rgb = image.convert("RGB")
                rgb.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                compressed = BytesIO()
                rgb.save(compressed, format="JPEG", quality=quality, optimize=True)
                if len(compressed.getvalue()) < len(item.data):
                    item.replace(rgb, quality=quality)
                    optimized += 1
            except (OSError, ValueError, TypeError):
                continue
    if not optimized:
        shutil.copyfile(source, output)
        return CompressionResult(original, output.stat().st_size, 0)
    with tempfile.TemporaryDirectory(prefix="zaraex_pdf_") as directory:
        candidate = Path(directory) / "compressed.pdf"
        with candidate.open("wb") as destination:
            writer.write(destination)
        shutil.copyfile(candidate if candidate.stat().st_size < original else source, output)
    return CompressionResult(original, output.stat().st_size, optimized)
