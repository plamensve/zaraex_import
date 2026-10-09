"""Headless tests for persistent app footer and copyright attribution."""

import unittest
from unittest.mock import Mock, patch

from app import (
    APP_TITLE,
    APP_VERSION,
    APP_AUTHOR,
    COPYRIGHT_NOTICE,
    APP_FOOTER_TEXT,
    ZaraExApp,
)


class FooterTests(unittest.TestCase):
    def test_footer_contains_name_version_and_copyright(self):
        self.assertEqual(APP_TITLE, "ZaraEx Import Generator")
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(APP_AUTHOR, "Plamen Svetoslavov")
        self.assertEqual(
            COPYRIGHT_NOTICE,
            "© 2026 Plamen Svetoslavov. Всички права запазени.",
        )
        self.assertIn(f"Created by {APP_AUTHOR}", APP_FOOTER_TEXT)
        self.assertIn(f"Версия {APP_VERSION}", APP_FOOTER_TEXT)
        self.assertIn(COPYRIGHT_NOTICE, APP_FOOTER_TEXT)

    def test_footer_is_packed_at_bottom_and_displays_text(self):
        host = Mock()
        with (
            patch("app.tk.Frame") as frame_class,
            patch("app.tk.Label") as label_class,
            patch("app.ttk.Separator") as separator_class,
        ):
            ZaraExApp.build_footer(host)

        frame_class.assert_called_once_with(host, bg="#edf2f8")
        footer = frame_class.return_value
        footer.pack.assert_called_once_with(side="bottom", fill="x")
        separator_class.assert_called_once_with(footer, orient="horizontal")
        label_class.assert_called_once()
        self.assertEqual(label_class.call_args.kwargs["text"], APP_FOOTER_TEXT)
        self.assertEqual(label_class.call_args.kwargs["anchor"], "e")
        label_class.return_value.pack.assert_called_once_with(fill="x")


if __name__ == "__main__":
    unittest.main()
