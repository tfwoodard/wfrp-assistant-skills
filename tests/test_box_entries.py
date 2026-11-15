"""Tests for a box whose headings each start an entry (adventure hooks), on an invented page.

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

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {'source': 'TEST', 'chapter': 'ch9',
        'entries': [{'name': 'Old Hanne', 'page': 1, 'category': 'lore', 'kind': 'other'}],
        'boxes': {'1.1': {'entries': {'category': 'lore', 'kind': 'other', 'audience': 'gm'}}},
        'relations': {'lore/the-missing-cask': [{'role': 'adds-to', 'to': 'lore/old-hanne'}]}}


def draw_page(path, stray=True, headings=True):
    """Left column: an entry whose paragraph's last line is set over the top of a panel; in the
    panel, two hooks under their own headings (the second heading over two lines). Right column:
    the entry carries on under a subheading."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    text(150, h - 70, 'THE LANTERN TRADES', 'Helvetica-Bold', 30)
    text(50, h - 110, 'Old Hanne', 'Helvetica-Bold', 19)
    text(50, h - 126, 'Hanne has kept the north tower for forty years')
    c.drawImage(ImageReader(Image.new('RGB', (40, 40), (230, 220, 190))), 44, h - 250, 250, 119)
    y = h - 137
    if stray:
        text(50, y, 'and keeps the tide tables.')
    y -= 18
    if headings:
        text(50, y, 'THE MISSING CASK', 'Helvetica-Bold', 12)
    y -= 12
    text(50, y, 'A cask of whale oil has gone from the store.'); y -= 18
    if headings:
        text(50, y, 'A LIGHT', 'Helvetica-Bold', 12); y -= 13
        text(50, y, 'AT SEA', 'Helvetica-Bold', 12)
    y -= 12
    text(50, y, 'Someone answers the beacon from the water.')
    text(320, h - 110, 'Hanne as Patron', 'Helvetica-Bold', 14)
    text(320, h - 126, 'She pays in lamp oil and good advice.')
    for k in range(1, 5):
        text(320, h - 126 - 11 * k, 'Gulls circle the tower all day.')
    c.setFont('Helvetica', 9)
    c.drawString(w / 2, 20, '1')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class BoxEntriesTest(unittest.TestCase):
    def convert(self, d, **draw):
        pdf, layout, planf, out = (os.path.join(d, n) for n in ('p.pdf', 'layout.json', 'plan.json', 'out'))
        draw_page(pdf, **draw)
        self.assertEqual(run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', layout).returncode, 0)
        with open(planf, 'w') as f:
            json.dump(PLAN, f)
        r = run('convert_rules.py', layout, '--plan', planf, '--out', out)
        with open(os.path.join(out, '_report.json')) as f:
            return r, json.load(f), out, layout

    def test_each_heading_is_an_entry_and_the_stray_line_goes_home(self):
        with tempfile.TemporaryDirectory() as d:
            r, report, out, layout = self.convert(d)
            self.assertEqual(report['errors'], [], r.stdout)
            with open(os.path.join(out, '_records.json')) as f:
                recs = {x['slug']: x for x in json.load(f)}
            self.assertEqual(set(recs), {'old-hanne', 'the-missing-cask', 'a-light-at-sea'})
            self.assertEqual(recs['a-light-at-sea']['audience'], 'gm')
            self.assertEqual(recs['the-missing-cask']['relations'], [{'role': 'adds-to', 'to': 'lore/old-hanne'}])
            self.assertNotIn('audience', recs['old-hanne'])
            with open(os.path.join(out, 'lore--old-hanne.json')) as f:
                hanne = json.load(f)['content']
            # The line set over the box's edge rejoins its paragraph; the hooks take nothing after them.
            self.assertEqual(hanne[0]['text'], 'Hanne has kept the north tower for forty years and keeps the tide tables.')
            self.assertEqual((hanne[1]['type'], hanne[1]['text']), ('heading', 'Hanne as Patron'))
            self.assertTrue(hanne[2]['text'].startswith('She pays in lamp oil'))
            with open(os.path.join(out, 'lore--a-light-at-sea.json')) as f:
                light = json.load(f)
            self.assertEqual(light['name'], 'A Light at Sea')
            self.assertEqual([b['text'] for b in light['content']], ['Someone answers the beacon from the water.'])
            self.assertEqual(report['returned_to_text'], [{'box': '1.1', 'entry': 'Old Hanne',
                                                           'text': 'and keeps the tide tables.'}])
            self.assertIn('every word', run('check_coverage.py', layout, out).stdout)

    def test_a_box_with_no_heading_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            r, report, _, _ = self.convert(d, headings=False)
            self.assertEqual(r.returncode, 1)
            self.assertIn('no heading', report['errors'][0]['error'])


if __name__ == '__main__':
    unittest.main()
