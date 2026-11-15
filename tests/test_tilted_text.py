"""Tests for reading notes printed at an angle, on an invented page.

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

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

BODY = ['The keeper climbs the stair at dusk', 'and trims each wick in turn.']
LEFT_NOTE = ['Oil runs low again. Ask the', 'chandler for two more casks', 'before the frost.', None,
             'The gulls stole my bread.']
RIGHT_NOTE = ['Mend the east shutter', 'when the wind drops.']
PINNED = 'Lamp Log'


def note(c, x, y, angle, lines, size=10, leading=14):
    """Lines of a note turned `angle` degrees about (x, y); None leaves a blank line."""
    c.saveState()
    c.translate(x, y)
    c.rotate(angle)
    c.setFont('Helvetica', size)
    for k, text in enumerate(lines):
        if text:
            c.drawString(0, -leading * k, text)
    c.restoreState()


def draw_page(path):
    """Level body text; under it two notes side by side at the same angle and one at another;
    a larger title pinned, tilted, over the top margin."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFont('Helvetica', 10)
    for k, text in enumerate(BODY):
        c.drawString(60, h - 150 - 14 * k, text)
    note(c, 380, h - 30, -2, [PINNED], size=20)
    note(c, 70, h - 300, 4, LEFT_NOTE)
    note(c, 330, h - 280, 4, RIGHT_NOTE)
    note(c, 300, h - 420, 12, ['A long line that climbs well above the note beside it.'])
    note(c, 60, h - 400, 0.2, ['Barely tilted: level enough.'])
    note(c, 90, h - 500, -7, ['Wicks: forty. Casks: three.'])
    c.setFont('Helvetica', 9)
    c.drawString(w / 2, 30, '1')
    c.showPage()
    c.save()


def layout(d):
    pdf, out = os.path.join(d, 'page.pdf'), os.path.join(d, 'layout.json')
    draw_page(pdf)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pdf_layout.py'), pdf, '--pages', '1',
                        '--boxes', '--out', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with open(out, encoding='utf-8') as f:
        return json.load(f)


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class TiltedTextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            cls.doc = layout(d)
        cls.lines = [l for l in cls.doc['lines'] if not l['furniture']]

    def scrap(self, first):
        sid = next(l['scrap'] for l in self.lines if l['text'] == first)
        return [l for l in self.lines if l.get('scrap') == sid]

    def test_tilted_lines_read_whole(self):
        texts = [l['text'] for l in self.lines]
        for text in BODY + [t for t in LEFT_NOTE if t] + RIGHT_NOTE + [PINNED, 'Wicks: forty. Casks: three.']:
            self.assertIn(text, texts)

    def test_level_text_carries_no_tilt(self):
        for l in self.lines:
            self.assertEqual('tilt' in l, l['text'] not in BODY + ['Barely tilted: level enough.'], l['text'])

    def test_each_note_is_a_scrap_with_its_angle(self):
        left, right = self.scrap(LEFT_NOTE[0]), self.scrap(RIGHT_NOTE[0])
        self.assertEqual([l['text'] for l in left], [t for t in LEFT_NOTE if t])
        self.assertEqual([l['text'] for l in right], RIGHT_NOTE)
        self.assertEqual({l['tilt'] for l in left + right}, {4.0})
        self.assertEqual({l['tilt'] for l in self.scrap('Wicks: forty. Casks: three.')}, {-7.0})
        self.assertEqual(len({l['scrap'] for l in self.lines if 'scrap' in l}), 5)

    def test_a_note_is_placed_by_where_its_first_line_starts(self):
        # The climbing line's far end is higher than the level line's start, but it starts lower.
        texts = [l['text'] for l in self.lines]
        self.assertLess(texts.index('Barely tilted: level enough.'), texts.index(PINNED))
        order = [l['text'] for l in self.lines if l.get('scrap')]
        self.assertLess(order.index(LEFT_NOTE[-1]), order.index('A long line that climbs well above the note beside it.'))
        self.assertLess(order.index('A long line that climbs well above the note beside it.'),
                        order.index('Wicks: forty. Casks: three.'))

    def test_scraps_follow_the_body_from_the_top_of_the_page_down(self):
        firsts = []
        for l in self.lines:
            if l.get('scrap') and l['scrap'] not in [s for s, _ in firsts]:
                firsts.append((l['scrap'], l['text']))
        self.assertEqual([t for _, t in firsts], [PINNED, RIGHT_NOTE[0], LEFT_NOTE[0],
                                                  'A long line that climbs well above the note beside it.',
                                                  'Wicks: forty. Casks: three.'])
        self.assertEqual([l['text'] for l in self.lines[:2]], BODY)

    def test_a_note_over_the_top_margin_is_not_furniture_and_keeps_its_type_size(self):
        pinned = next(l for l in self.doc['lines'] if l['text'] == PINNED)
        self.assertFalse(pinned['furniture'])
        self.assertEqual(pinned['size'], 20.0)
        self.assertEqual(pinned['heading'], 1)
        self.assertEqual({l['size'] for l in self.scrap(LEFT_NOTE[0])}, {10.0})

    def test_a_scrap_is_its_own_paragraphs(self):
        report = {'questions': [], 'dehyphenated': []}
        notes = [l for l in self.lines if l.get('scrap') and 'heading' not in l]
        blocks = entry_text.blocks_from_lines(notes, report, 'page 1')
        self.assertEqual([b['text'] for b in blocks if b['type'] == 'paragraph'],
                         ['Mend the east shutter when the wind drops.',
                          'Oil runs low again. Ask the chandler for two more casks before the frost.',
                          'The gulls stole my bread.', 'A long line that climbs well above the note beside it.',
                          'Wicks: forty. Casks: three.'])


if __name__ == '__main__':
    unittest.main()
