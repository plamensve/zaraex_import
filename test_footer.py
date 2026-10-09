"""Headless checks for the concise, persistent copyright footer."""

import unittest
from unittest.mock import Mock, call, patch

from app import (
    APP_TITLE,
    APP_VERSION,
    APP_VERSION_LABEL,
    APP_AUTHOR,
    COPYRIGHT_NOTICE,
    ZaraExApp,
)


class FooterTests(unittest.TestCase):
    def test_footer_contains_one_owner_and_separate_version(self):
        self.assertEqual(APP_TITLE, "ZaraEx Import Generator")
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(APP_AUTHOR, "Plamen Svetoslavov")
        self.assertEqual(
            COPYRIGHT_NOTICE,
            "© 2026 Plamen Svetoslavov. Всички права запазени.",
        )
        self.assertEqual(APP_VERSION_LABEL, "Версия 1.0.0")
        self.assertEqual(COPYRIGHT_NOTICE.count(APP_AUTHOR), 1)
        self.assertNotIn(APP_AUTHOR, APP_VERSION_LABEL)
        self.assertNotIn("Created by", COPYRIGHT_NOTICE)

    def test_footer_has_left_copyright_and_right_version(self):
        host = Mock()
        footer = Mock()
        content = Mock()
        left_label = Mock()
        right_label = Mock()

        with (
            patch("app.tk.Frame", side_effect=[footer, content]) as frames,
            patch("app.tk.Label", side_effect=[left_label, right_label]) as labels,
            patch("app.ttk.Separator") as separators,
        ):
            ZaraExApp.build_footer(host)

        self.assertEqual(
            frames.call_args_list,
            [call(host, bg="#f4f7fb"), call(footer, bg="#f4f7fb")],
        )
        footer.pack.assert_called_once_with(side="bottom", fill="x")
        separators.assert_called_once_with(footer, orient="horizontal")
        separators.return_value.pack.assert_called_once_with(fill="x")
        content.pack.assert_called_once_with(fill="x")

        self.assertEqual(len(labels.call_args_list), 2)
        left_call, right_call = labels.call_args_list
        self.assertEqual(left_call.args[0], content)
        self.assertEqual(left_call.kwargs["text"], COPYRIGHT_NOTICE)
        self.assertEqual(left_call.kwargs["anchor"], "w")
        left_label.pack.assert_called_once_with(side="left")

        self.assertEqual(right_call.args[0], content)
        self.assertEqual(right_call.kwargs["text"], APP_VERSION_LABEL)
        self.assertEqual(right_call.kwargs["anchor"], "e")
        right_label.pack.assert_called_once_with(side="right")


if __name__ == "__main__":
    unittest.main()
