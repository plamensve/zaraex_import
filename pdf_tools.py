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
class ImagePage:
    source: str
    frame: int = 0


def image_pages(paths):
    """List each image frame as a separate PDF page, preserving file order."""
    pages = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file():
            raise ValueError("Невалидно изображение: " + path.name)
        try:
            with Image.open(path) as image:
                # Decode the first frame to detect invalid image content early.
                image.load()
                pages.extend(ImagePage(str(path), index)
                             for index in range(getattr(image, "n_frames", 1)))
        except (OSError, ValueError) as exc:
            raise ValueError("Неуспешно отваряне: " + path.name) from exc
    return pages



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
    """Export image frames in preview order; old path-list callers still work."""
    pages = []
    for item in paths:
        if isinstance(item, ImagePage):
            pages.append(item)
        else:
            pages.extend(image_pages([item]))
    if not pages:
        raise ValueError("Изберете поне едно изображение.")
    if not 30 <= dpi <= 600 or not 25 <= quality <= 95:
        raise ValueError("Невалидни настройки.")
    output = Path(output_path).expanduser().resolve()
    if any(os.path.normcase(os.path.abspath(p.source)) ==
           os.path.normcase(os.path.abspath(output)) for p in pages):
        raise ValueError("Изходният файл трябва да е различен от входния.")
    frames = []
    for item in pages:
        path = Path(item.source)
        if path.suffix.lower() not in IMAGE_EXTENSIONS or not path.is_file():
            raise ValueError("Неподдържано изображение: " + path.name)
        try:
            with Image.open(path) as image:
                image.seek(item.frame)
                frames.append(_rgb(image.copy()))
        except (OSError, ValueError, EOFError) as exc:
            raise ValueError("Неуспешно отваряне: " + path.name) from exc
    frames[0].save(str(output), "PDF", save_all=True,
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
