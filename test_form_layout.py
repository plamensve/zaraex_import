"""Headless checks for the alignment and coverage of the loading form grid."""

import unittest

from app import LOADING_FORM_COLUMNS, LOADING_FORM_FIELDS


class LoadingFormLayoutTests(unittest.TestCase):
    def test_all_expected_fields_present_once(self):
        expected = {
            "date", "ukn", "add", "quantity", "zara", "product", "base",
            "company", "vehicle", "driver", "handover_name", "handover_egn",
        }
        self.assertEqual({field[0] for field in LOADING_FORM_FIELDS}, expected)
        self.assertEqual(len(LOADING_FORM_FIELDS), len(expected))

    def test_rows_have_full_width_without_overlaps(self):
        self.assertEqual(LOADING_FORM_COLUMNS, 12)
        for row in range(3):
            occupied = []
            for key, label, kind, field_row, col, span in LOADING_FORM_FIELDS:
                if field_row == row:
                    self.assertTrue(label)
                    self.assertIn(kind, ("entry", "combo"))
                    self.assertGreater(span, 0)
                    occupied.extend(range(col, col + span))
            self.assertEqual(
                sorted(occupied), list(range(LOADING_FORM_COLUMNS)),
                f"Row {row} must have no gaps or overlapping fields",
            )

    def test_selector_and_handover_field_positions(self):
        field_map = {key: (kind, row) for key, _, kind, row, _, _ in LOADING_FORM_FIELDS}
        self.assertEqual(
            {key for key, (kind, _) in field_map.items() if kind == "combo"},
            {"product", "base", "company", "vehicle", "driver"},
        )
        self.assertEqual(field_map["handover_name"], ("entry", 2))
        self.assertEqual(field_map["handover_egn"], ("entry", 2))


if __name__ == "__main__":
    unittest.main()
