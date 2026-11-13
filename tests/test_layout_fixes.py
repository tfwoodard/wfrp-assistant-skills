"""Tests for reading pictures, capitals and bullets right, on an invented page and invented strings.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts')
sys.path.insert(0, SCRIPTS)

import entry_text  # noqa: E402
import pdf_layout  # noqa: E402

try:
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False


def draw_page(path):
    """A two-column page. Left: a lantern-keeper picture cut out with a soft mask (a figure in a
    mostly see-through rectangle) whose rectangle runs over the start of the right column's lines.
    Right, lower down: a sidebar on an opaque panel."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    pic = Image.new('RGBA', (200, 300), (0, 0, 0, 0))
    ImageDraw.Draw(pic).ellipse((60, 40, 140, 260), fill=(90, 60, 30, 255))     # the figure
    c.drawImage(ImageReader(pic), 60, h - 400, 270, 300, mask='auto')          # x 60-330
    panel = Image.new('RGB', (40, 40), (230, 220, 190))
    c.drawImage(ImageReader(panel), 310, h - 700, 230, 150)                   # x 310-540
    c.setFont('Helvetica', 9)
    for k in range(20):
        c.drawString(50, h - 120 - 11 * k, 'Keepers trim the wicks at dusk.')
        c.drawString(306, h - 120 - 11 * k, 'Gulls circle the tower all day.')
    c.setFont('Helvetica-Bold', 10)
    c.drawString(320, h - 570, 'Storm Lamps')
    c.setFont('Helvetica', 9)
    c.drawString(320, h - 585, 'Light both lamps when the bell rings.')
    c.showPage()
    c.save()


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class IllustrationTest(unittest.TestCase):
    def test_a_cut_out_picture_is_not_a_box_but_an_opaque_panel_is(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, out = os.path.join(d, 'page.pdf'), os.path.join(d, 'layout.json')
            draw_page(pdf)
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pdf_layout.py'), pdf, '--pages', '1',
                                '--boxes', '--out', out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('illustration', r.stderr)
            with open(out) as f:
                doc = json.load(f)
        self.assertEqual(len(doc['regions']), 1)                                  # the panel only
        self.assertEqual(len(doc['image_notes']), 1)
        boxed = [l['text'] for l in doc['lines'] if l.get('box')]
        self.assertEqual(boxed, ['Storm Lamps', 'Light both lamps when the bell rings.'])
        right = [l['text'] for l in doc['lines'] if l['column'] == 'right' and not l.get('box')]
        self.assertEqual(right, ['Gulls circle the tower all day.'] * 20)         # no words lost to the picture


class CapitalsTest(unittest.TestCase):
    def test_a_capitals_code_read_as_lower_case_keeps_its_capital(self):
        class Font:
            basefont = 'LampFace'

        class SmallCaps:
            basefont = 'LampFace-SC700'

        saved = pdf_layout._to_unichr
        pdf_layout._to_unichr = lambda self, cid: chr(cid).lower()    # a character map that lowers capitals
        try:
            pdf_layout.CASE_FIXED.clear()
            read = pdf_layout._to_unichr_keeping_capitals
            self.assertEqual(''.join(read(Font(), c) for c in b'Keeper'), 'Keeper')
            self.assertEqual(''.join(read(SmallCaps(), c) for c in b'Keeper'), 'keeper')   # left alone
            self.assertEqual(pdf_layout.CASE_FIXED, {'LampFace': 1})
        finally:
            pdf_layout._to_unichr = saved

    def test_titles_in_capitals_are_title_cased(self):
        self.assertEqual(entry_text.fix_case('OPTIONS: STORM LAMPS (TOWER)'), 'Options: Storm Lamps (Tower)')
        self.assertEqual(entry_text.fix_case('OIL COSTS IN XP'), 'Oil Costs in XP')
        self.assertEqual(entry_text.fix_case('Who Trims the Wick?'), 'Who Trims the Wick?')


class BulletTest(unittest.TestCase):
    def test_a_bullet_goes_but_its_bold_stays(self):
        self.assertEqual(entry_text.strip_bullet('**• Wick**: the part that burns'), '**Wick**: the part that burns')
        self.assertEqual(entry_text.strip_bullet('**•** **Wick**: x'), '**Wick**: x')
        self.assertEqual(entry_text.strip_bullet('• **Oil**: 2'), '**Oil**: 2')
        self.assertEqual(entry_text.strip_bullet('• plain item'), 'plain item')


if __name__ == '__main__':
    unittest.main()
