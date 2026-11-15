"""Tests for a three-column timeline page: a standfirst set across the columns doesn't hide the
gutters, a dash set a little above the line joins it ("-40"), a plan's "headings_as_rows" makes the
dates and events a table, a backdrop read as text keeps its page column, and a box made an entry
carries its "audience". The page is invented and drawn by the test: no book text.

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

from entry_text import fix_case  # noqa: E402

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

COLS = (60, 230, 400)
FILLER = ['The lamplighters met at the mill', 'and agreed on one wick length',
          'for every towpath lantern,', 'which pleased the bargemen.']
PLAN = {
    'source': 'TEST', 'chapter': 'ch10',
    'entries': [{'name': 'Lamp Timeline', 'page': 1, 'category': 'lore', 'kind': 'history',
                 'headings_as_rows': ['Date', 'Event']}],
    'not_headings': [{'page': 1, 'text': 'A summary of the years of the lamplighters.'}],
    'boxes': {'1.1': {'text': True},
              '1.2': {'entry': {'name': 'Wick Secrets', 'category': 'lore', 'kind': 'other',
                                'audience': 'gm'}}},
}


def draw(path):
    """Title and standfirst across the page; three columns of dated events, the first dates
    with a raised minus sign; one line of the middle column over a tinted backdrop; a GM box
    at the foot of the right column."""
    img = os.path.join(os.path.dirname(path), 'tint.png')
    Image.new('RGB', (40, 40), (225, 215, 185)).save(img)
    c = canvas.Canvas(path, pagesize=A4)

    def text(x, y, s, font='Helvetica', size=10):
        c.setFont(font, size)
        c.drawString(x, y, s)

    def date(x, y, years, minus=False):
        if minus:
            text(x, y + 2, '-', 'Helvetica-Bold', 14)
            x += stringWidth('-', 'Helvetica-Bold', 14)
        text(x, y, f'{years} YR', 'Helvetica-Bold', 14)

    text(150, 760, 'LAMP TIMELINE', 'Helvetica-Bold', 18)
    text(120, 744, 'A summary of the years of the lamplighters.', 'Helvetica-Oblique', 11)
    year = 40
    for col, x in enumerate(COLS):
        y = 715
        for k in range(5):
            minus = col == 0 and k < 2
            if col == 1 and k == 2:            # a backdrop behind a date and its first line
                c.drawImage(img, x - 4, y - 17, 160, 29)
            date(x, y, year if minus else year * 3, minus)
            y -= 14
            for line in FILLER:
                text(x, y, line)
                y -= 12
            year -= 3
            y -= 4
    c.drawImage(img, COLS[2] - 6, 250, 170, 60)
    text(COLS[2], 295, 'WICK SECRETS', 'Helvetica-Bold', 12)
    text(COLS[2], 281, 'The guild hides its best wicks', size=9)
    text(COLS[2], 270, 'in the mill loft, behind the sacks.', size=9)
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


class FixCaseTest(unittest.TestCase):
    def test_a_year_heading_keeps_its_abbreviation_and_era(self):
        self.assertEqual(fix_case('c. 12 IC'), 'c. 12 IC')
        self.assertEqual(fix_case('c. 12 ic'), 'c. 12 IC')


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class TimelinePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        pdf = os.path.join(d, 'page.pdf')
        draw(pdf)
        cls.layout = os.path.join(d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', cls.layout)
        assert r.returncode == 0, r.stderr
        with open(cls.layout) as f:
            cls.doc = json.load(f)
        with open(os.path.join(d, 'plan.json'), 'w') as f:
            json.dump(PLAN, f)
        cls.out = os.path.join(d, 'out')
        cls.result = run('convert_rules.py', cls.layout, '--plan', os.path.join(d, 'plan.json'), '--out', cls.out)
        with open(os.path.join(cls.out, '_report.json')) as f:
            cls.report = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, name):
        with open(os.path.join(self.out, name)) as f:
            return json.load(f)

    def test_the_standfirst_does_not_hide_the_gutters(self):
        self.assertEqual(len(self.doc['gutters']['1']), 2, self.doc['gutters'])

    def test_a_raised_minus_joins_its_date(self):
        texts = [l['text'] for l in self.doc['lines']]
        self.assertIn('-40 YR', texts)
        self.assertNotIn('-', texts)

    def test_converts_without_errors_and_accounts_for_every_word(self):
        self.assertEqual(self.report['errors'], [])
        r = run('check_coverage.py', self.layout, self.out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dates_and_events_become_one_table_in_reading_order(self):
        content = self.load('lore--lamp-timeline.json')['content']
        self.assertEqual([b['type'] for b in content], ['paragraph', 'table'])
        rows = content[1]['rows']
        self.assertEqual([r[0] for r in rows[:3]], ['-40 YR', '-37 YR', '102 YR'])
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(r[1].startswith('The lamplighters met at the mill and agreed') for r in rows), rows)
        self.assertEqual(content[1]['columns'], ['Date', 'Event'])

    def test_a_backdrop_read_as_text_stays_in_its_column(self):
        rows = self.load('lore--lamp-timeline.json')['content'][1]['rows']
        self.assertEqual([r[0] for r in rows[5:10]], ['75 YR', '66 YR', '57 YR', '48 YR', '39 YR'])
        self.assertEqual(rows[7][1], rows[0][1])

    def test_a_box_entry_carries_its_audience(self):
        entry = self.load('lore--wick-secrets.json')
        self.assertEqual(entry['audience'], 'gm')
        with open(os.path.join(self.out, '_records.json')) as f:
            rec = next(r for r in json.load(f) if r['slug'] == 'wick-secrets')
        self.assertEqual(rec['audience'], 'gm')


if __name__ == '__main__':
    unittest.main()
