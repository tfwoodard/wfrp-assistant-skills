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
    c.drawString(320, h - 600, '99')                                        # a table's number, mid-page
    c.drawString(w / 2, 30, '1')                                            # the page number
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
        self.assertEqual(boxed, ['Storm Lamps', 'Light both lamps when the bell rings.', '99'])
        furniture = {l['text']: l['furniture'] for l in doc['lines'] if l['text'] in ('1', '99')}
        self.assertEqual(furniture, {'1': True, '99': False})          # only the page's own number
        right = [l['text'] for l in doc['lines'] if l['column'] == 'right' and not l.get('box') and not l['furniture']]
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


class HeadingSizeTest(unittest.TestCase):
    def test_a_boxs_body_size_is_never_a_heading_size(self):
        def line(text, size, box=None):
            return {'text': text, 'size': size, 'furniture': False, 'box': box,
                    'spans': [{'text': text, 'size': size, 'bold': size > 9}]}
        body = [line('Keepers keep the lamps lit through every storm of the year.', 9.0) for _ in range(60)]
        title = line('Storm Lamps', 15.0, 'b1')
        boxed = [line('Light both lamps when the bell rings, and trim them at dawn.', 10.0, 'b1') for _ in range(5)]
        head = line('Wicks', 12.0)
        pdf_layout.assign_headings(body + [head, title] + boxed)
        self.assertIn('heading', head)
        self.assertIn('heading', title)
        self.assertFalse(any('heading' in l for l in boxed))    # rare on the pages, but the box's text


class TitleCaseTest(unittest.TestCase):
    def test_after_a_colon_and_known_acronyms(self):
        self.assertEqual(entry_text.fix_case('optIons: on the deFensIve'), 'Options: On the Defensive')
        self.assertEqual(entry_text.fix_case('roll FOr wIcks!'), 'Roll for Wicks!')
        self.assertEqual(entry_text.fix_case('CharaCteristiC Xp'), 'Characteristic XP')


class BulletTest(unittest.TestCase):
    def test_a_bullet_goes_but_its_bold_stays(self):
        self.assertEqual(entry_text.strip_bullet('**• Wick**: the part that burns'), '**Wick**: the part that burns')
        self.assertEqual(entry_text.strip_bullet('**•** **Wick**: x'), '**Wick**: x')
        self.assertEqual(entry_text.strip_bullet('• **Oil**: 2'), '**Oil**: 2')
        self.assertEqual(entry_text.strip_bullet('• plain item'), 'plain item')


if __name__ == '__main__':
    unittest.main()


def draw_columns_page(path):
    """Page 1: three columns of text. Page 2: two columns, the left one's lines running across an
    opaque picture rectangle in its lower half; then a sidebar panel in the right column holding a
    three-column table."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFont('Helvetica', 9)
    for k in range(30):
        c.drawString(50, h - 80 - 11 * k, 'Ropes coil on the')
        c.drawString(225, h - 80 - 11 * k, 'quay where nets')
        c.drawString(400, h - 80 - 11 * k, 'dry in the wind.')
    c.showPage()
    pic = Image.new('RGB', (40, 40), (120, 140, 160))
    c.drawImage(ImageReader(pic), 130, h - 500, 160, 200)                     # x 130-290, across "wicks"
    panel = Image.new('RGB', (40, 40), (230, 220, 190))
    c.drawImage(ImageReader(panel), 310, h - 760, 230, 120)                   # x 310-540
    c.setFont('Helvetica', 9)
    for k in range(30):
        c.drawString(50, h - 120 - 11 * k, 'Keepers trim the wicks at dusk and dawn.')
        c.drawString(306, h - 120 - 11 * k, 'Gulls circle the tower all day.')
    for k, row in enumerate((('Oil', 'Wick', 'Glass'), ('1', '2', '3'), ('4', '5', '6'))):
        for x, cell in zip((320, 395, 470), row):
            c.drawString(x, h - 660 - 13 * k, cell)
    c.showPage()
    c.save()


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class ColumnsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pdf, out = os.path.join(self.tmp.name, 'page.pdf'), os.path.join(self.tmp.name, 'layout.json')
        draw_columns_page(pdf)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pdf_layout.py'), pdf, '--pages', '1-2',
                            '--boxes', '--out', out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out) as f:
            self.doc = json.load(f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_page_in_three_columns(self):
        self.assertEqual(len(self.doc['gutters']['1']), 2)
        cols = {l['text']: l['column'] for l in self.doc['lines'] if l['page'] == 1}
        self.assertEqual(cols, {'Ropes coil on the': 'left', 'quay where nets': 'middle',
                                'dry in the wind.': 'right'})

    def test_text_running_over_a_picture_makes_it_no_box(self):
        self.assertEqual(len(self.doc['gutters']['2']), 1)
        self.assertEqual(len(self.doc['regions']), 1)                         # the panel only
        self.assertTrue(any('text runs over its edges' in n for n in map(str, self.doc['image_notes'])),
                        self.doc['image_notes'])
        left = [l['text'] for l in self.doc['lines'] if l['page'] == 2 and l['column'] == 'left']
        self.assertEqual(left, ['Keepers trim the wicks at dusk and dawn.'] * 30)

    def test_a_table_in_a_box_is_not_read_as_three_text_columns(self):
        boxed = [l['text'] for l in self.doc['lines'] if l.get('box')]
        self.assertEqual(boxed, ['Oil Wick Glass', '1 2 3', '4 5 6'])


class SlugTest(unittest.TestCase):
    def test_accents_and_apostrophes_are_dropped(self):
        self.assertEqual(entry_text.slugify('Lamp-Wright’s Öil'), 'lamp-wrights-oil')
        self.assertEqual(entry_text.slugify("Gull's Câll"), 'gulls-call')


def draw_titled_tables(path):
    """One parchment panel holding two ruled tables, each under its own large title, with
    different column positions; plus enough body text for the page's columns."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    panel = Image.new('RGB', (40, 40), (230, 220, 190))
    c.drawImage(ImageReader(panel), 60, h - 520, 470, 440)
    c.setLineWidth(0.5)

    def table(top, title, cols, rows):
        c.setFont('Helvetica', 16)
        c.drawString(200, top, title)
        y = top - 24
        c.setFont('Helvetica-Bold', 9)
        for x, name in zip(cols, ('Lamp', 'Oil', 'Keeper')):
            c.drawString(x + 3, y, name)
        y -= 5
        c.setFont('Helvetica', 9)
        for row in rows:
            c.line(70, y, 520, y)
            y -= 12
            for x, cell in zip(cols, row):
                c.drawString(x + 3, y, cell)
            y -= 5
        c.line(70, y, 520, y)
        for x in cols[1:]:
            c.line(x, top - 29, x, y)

    table(h - 110, 'NORTH LAMPS', [70, 170, 330], [('Gull', 'Tallow', 'Ada'), ('Rock', 'Rush', 'Bo')])
    table(h - 260, 'SOUTH LAMPS', [70, 220, 400], [('Bay', 'Whale', 'Cy'), ('Spit', 'Seal', 'Di'), ('Pier', 'Fish', 'Ed')])
    c.setFont('Helvetica', 9)
    for k in range(14):
        c.drawString(60, h - 560 - 11 * k, 'Keepers trim the wicks at dusk.')
        c.drawString(310, h - 560 - 11 * k, 'Gulls circle the tower all day.')
    c.showPage()
    c.save()


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class TitledTablesTest(unittest.TestCase):
    def test_a_box_of_titled_tables_is_one_region_per_table(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, out = os.path.join(d, 'page.pdf'), os.path.join(d, 'layout.json')
            draw_titled_tables(pdf)
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pdf_layout.py'), pdf, '--pages', '1',
                                '--boxes', '--out', out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as f:
                doc = json.load(f)
        regions = {x['id']: x for x in doc['regions']}
        self.assertEqual(sorted(regions), ['1.1.1', '1.1.2'])
        self.assertEqual(regions['1.1.1']['columns'], ['Lamp', 'Oil', 'Keeper'])
        self.assertEqual(regions['1.1.1']['rows'], [['Gull', 'Tallow', 'Ada'], ['Rock', 'Rush', 'Bo']])
        self.assertEqual([r[0] for r in regions['1.1.2']['rows']], ['Bay', 'Spit', 'Pier'])
        boxes = {l['text']: l['box'] for l in doc['lines'] if l.get('box')}
        self.assertEqual((boxes['NORTH LAMPS'], boxes['SOUTH LAMPS']), ('1.1.1', '1.1.2'))
