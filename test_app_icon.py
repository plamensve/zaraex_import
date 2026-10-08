import os
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app_icon_path


class ApplicationIconTests(unittest.TestCase):
    def test_icon_is_a_valid_multisize_windows_ico(self):
        icon = Path(app_icon_path())
        self.assertTrue(icon.is_file())
        content = icon.read_bytes()
        reserved, icon_type, count = struct.unpack_from("<HHH", content)
        self.assertEqual((reserved, icon_type), (0, 1))
        sizes = set()
        for i in range(count):
            width, height, colors, reserved, planes, bit_count, length, offset = struct.unpack_from(
                "<BBBBHHII", content, 6 + 16 * i
            )
            sizes.add((width or 256, height or 256))
            self.assertEqual(content[offset:offset + 8], b"\x89PNG\r\n\x1a\n")
            self.assertLessEqual(offset + length, len(content))
        self.assertEqual(sizes, {(16, 16), (32, 32), (48, 48), (256, 256)})

    def test_icon_path_uses_pyinstaller_resource_directory(self):
        with patch.object(sys, "_MEIPASS", os.path.join("tmp", "bundle"), create=True):
            self.assertEqual(
                app_icon_path(),
                os.path.join("tmp", "bundle", "ZaraExImport.ico"),
            )


if __name__ == "__main__":
    unittest.main()
