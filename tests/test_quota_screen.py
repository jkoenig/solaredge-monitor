"""Tests for the "Kontingent aufgebraucht" info screen (stdlib unittest)."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from rendering.fonts import load_font  # noqa: E402
from screens.error import QUOTA_HEADLINE, render_quota_exhausted_screen  # noqa: E402

_ORIGINAL_TEXT = ImageDraw.ImageDraw.text


def drawn_texts(render, data):
    with mock.patch.object(
        ImageDraw.ImageDraw, "text", autospec=True, side_effect=_ORIGINAL_TEXT
    ) as spy:
        render(data)
    return [
        c.kwargs["text"] if "text" in c.kwargs else c.args[2]
        for c in spy.call_args_list
    ]


def text_width(text, size):
    draw = ImageDraw.Draw(Image.new("1", (1000, 488), 1))
    bbox = draw.textbbox((0, 0), text, font=load_font("Arial.ttf", size))
    return bbox[2] - bbox[0]


class QuotaScreenTest(unittest.TestCase):
    def test_mode_and_size(self):
        img = render_quota_exhausted_screen(date(2026, 12, 5))
        self.assertEqual(img.mode, "1")
        self.assertEqual(img.size, (1000, 488))

    def test_copy(self):
        texts = drawn_texts(render_quota_exhausted_screen, date(2026, 12, 5))
        self.assertEqual(texts, ["Kontingent aufgebraucht", "Neue Werte ab 5.12."])

    def test_no_leading_zero_no_year(self):
        texts = drawn_texts(render_quota_exhausted_screen, date(2027, 1, 5))
        self.assertIn("Neue Werte ab 5.1.", texts)
        texts = drawn_texts(render_quota_exhausted_screen, date(2026, 12, 28))
        self.assertIn("Neue Werte ab 28.12.", texts)

    def test_widths_under_990(self):
        self.assertLess(text_width(QUOTA_HEADLINE, 60), 990)
        for msg in ("Neue Werte ab 5.12.", "Neue Werte ab 28.12."):
            self.assertLess(text_width(msg, 48), 990)

    def test_headline_pixels_and_not_blank(self):
        img = render_quota_exhausted_screen(date(2026, 12, 5))
        area = img.crop((0, 5, 1000, 70))
        self.assertIn(0, set(area.getdata()))
        self.assertIn(0, set(img.getdata()))


if __name__ == "__main__":
    unittest.main()
