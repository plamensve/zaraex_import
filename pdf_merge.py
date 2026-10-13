"""Non-destructive PDF page collection and ordered PDF merge."""
from dataclasses import dataclass
from pathlib import Path
import os
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class PdfPage:
    source: str
    number: int  # zero based within the original PDF


def _normalized(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def pages_from_pdf(path):
    """Enumerate all pages without decoding raster content."""
    source = Path(path).expanduser().resolve()
    if source.suffix.lower() != ".pdf" or not source.is_file():
        raise ValueError("Файлът не е валиден PDF: " + source.name)
    try:
        reader = PdfReader(str(source), strict=False)
        if reader.is_encrypted:
            raise ValueError("PDF файлът е защитен с парола: " + source.name)
        count = len(reader.pages)
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "защитен" in str(exc):
            raise
        raise ValueError("Неуспешно четене на PDF: " + source.name) from exc
    if count == 0:
        raise ValueError("PDF файлът няма страници: " + source.name)
    return [PdfPage(str(source), index) for index in range(count)]


class PdfPageCollection:
    """Ordered page list used by the thumbnail grid and exporter."""

    def __init__(self):
        self.pages = []

    def add_files(self, paths):
        appended = []
        for path in paths:
            # All-or-nothing per file. Previously imported files stay intact.
            new_pages = pages_from_pdf(path)
            self.pages.extend(new_pages)
            appended.extend(new_pages)
        return appended

    def move(self, old_index, new_index):
        """Move one page onto another page's position."""
        if not 0 <= old_index < len(self.pages):
            raise IndexError(old_index)
        if not 0 <= new_index < len(self.pages):
            raise IndexError(new_index)
        page = self.pages.pop(old_index)
        self.pages.insert(new_index, page)

    def remove(self, indices):
        for index in sorted(set(indices), reverse=True):
            if not 0 <= index < len(self.pages):
                raise IndexError(index)
            del self.pages[index]

    def clear(self):
        self.pages.clear()


def merge_pdf_pages(pages, output_path):
    """Merge selected pages in exact given order, retaining vectors and text.

    Write to a temporary adjacent file and atomically replace the target after
    successful completion. Never overwrite any source PDF, including symlinks.
    """
    selection = list(pages)
    if not selection:
        raise ValueError("Добавете поне една PDF страница.")
    target = Path(output_path).expanduser().resolve()
    if target.suffix.lower() != ".pdf":
        raise ValueError("Изходният файл трябва да е PDF.")
    if any(_normalized(page.source) == _normalized(target) for page in selection):
        raise ValueError("Изходният файл не може да презапише входен PDF.")
    readers = {}
    writer = PdfWriter()
    try:
        for item in selection:
            if item.source not in readers:
                reader = PdfReader(item.source, strict=False)
                if reader.is_encrypted:
                    raise ValueError("PDF файлът е защитен с парола: " + Path(item.source).name)
                readers[item.source] = reader
            reader = readers[item.source]
            if not 0 <= item.number < len(reader.pages):
                raise ValueError("Невалидна страница във файл: " + Path(item.source).name)
            writer.add_page(reader.pages[item.number])

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", prefix=".zaraex-",
                                         dir=target.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            try:
                writer.write(temp)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
        try:
            os.replace(temp_path, target)
        finally:
            temp_path.unlink(missing_ok=True)
        return len(selection)
    finally:
        writer.close()
