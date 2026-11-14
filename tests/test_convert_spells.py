"""Tests for convert_spells.py on an invented one-page chapter of lamp-keepers' spells and prayers
the test draws itself: no book text.

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
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {
    'source': 'TEST', 'chapter': 'ch8',
    'entries': [{'name': 'Lamp Magic', 'page': 1, 'kind': 'procedure'}],
    'lists': [
        {'name': 'Keeper Spells', 'page': 1, 'kind': 'petty'},
        {'name': 'Prayers of the Keeper', 'page': 1, 'kind': 'miracle', 'lore': 'the Keeper', 'entry': False},
    ],
}

LEFT, RIGHT = 50, 306


def draw_chapter(path, stray=False):
    """Left column: a chapter heading, a list of two spells (one Target line wrapping). Right
    column: a list of prayers without CN, one with its "Duration:" label not in bold."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    def label(x, y, lab, rest, font='Helvetica-Bold'):
        text(x, y, lab, font)
        text(x + c.stringWidth(lab, font, 9) + 3, y, rest)

    def spell(x, y, name, fields, body):
        text(x, y, name, 'Helvetica-Bold', 12); y -= 13
        for f in fields:
            label(x, y, *f); y -= 11
        for s in body:
            text(x, y, s); y -= 11
        return y - 6

    y = h - 80
    text(LEFT, y, 'Lamp Magic', 'Helvetica-Bold', 18); y -= 20
    for s in ('Keepers work small magics with', 'their lamps and the sea air.'):
        text(LEFT, y, s); y -= 11
    y -= 8
    text(LEFT, y, 'Keeper Spells', 'Helvetica-Bold', 15); y -= 17
    text(LEFT, y, 'Every keeper learns these first.'); y -= 17
    y = spell(LEFT, y, 'Glow', [('CN:', '0'), ('Range:', 'You'), ('Target:', 'You'), ('Duration:', '1 hour')],
              ['Your lamp glows without oil.'])
    if stray:
        text(LEFT, y, 'Oil Store', 'Helvetica-Bold', 12); y -= 13
        text(LEFT, y, 'A heading at spell level that is no spell.'); y -= 17
    spell(LEFT, y, 'Far Beam', [('CN:', '2'), ('Range:', '100 yards'), ('Target:', 'One ship within'),
                                ('', 'sight'), ('Duration:', 'Instant')],
          ['Your beam reaches a ship at sea.'])

    y = h - 80
    text(RIGHT, y, 'Prayers of the Keeper', 'Helvetica-Bold', 15); y -= 17
    y = spell(RIGHT, y, 'Calm Sea', [('Range:', 'You'), ('Target:', 'You'), ('Duration:', '1 hour', 'Helvetica')],
              ['The waves around the tower still.'])
    y = spell(RIGHT, y, 'Safe Harbour', [('Range:', '1 mile'), ('Target:', 'One boat'), ('Duration:', 'Instant')],
              ['A boat finds the harbour mouth.'])
    for k in range(6):
        text(RIGHT, y - 11 * k, 'Gulls circle the tower all day.')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class ConvertSpellsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(PLAN, f)

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, **draw):
        pdf = os.path.join(self.d, 'chapter.pdf')
        draw_chapter(pdf, **draw)
        self.layout = os.path.join(self.d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--out', self.layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.out = os.path.join(self.d, 'out')
        r = run('convert_spells.py', self.layout, '--plan', os.path.join(self.d, 'plan.json'), '--out', self.out)
        with open(os.path.join(self.out, '_report.json')) as f:
            return r, json.load(f)

    def load(self, name):
        with open(os.path.join(self.out, name)) as f:
            return json.load(f)

    def test_spells_and_prayers(self):
        r, report = self.convert()
        self.assertEqual(r.returncode, 0, report['errors'])
        rec = {(x['_category'], x['slug']): x for x in self.load('_records.json')}
        self.assertEqual(set(rec), {('rules', 'lamp-magic'), ('rules', 'keeper-spells'),
                                    ('spells', 'glow'), ('spells', 'far-beam'),
                                    ('spells', 'calm-sea'), ('spells', 'safe-harbour')})
        glow = rec[('spells', 'glow')]
        self.assertEqual((glow['kind'], glow['lore'], glow['cn'], glow['range']), ('petty', None, 0, 'You'))
        self.assertEqual(glow['section'], 'Keeper Spells')
        self.assertEqual(rec[('spells', 'far-beam')]['target'], 'One ship within sight')
        sea = rec[('spells', 'calm-sea')]
        self.assertEqual((sea['kind'], sea['lore'], sea['cn'], sea['duration']),
                         ('miracle', 'the Keeper', None, '1 hour'))
        self.assertEqual(sea['section'], 'Prayers of the Keeper')

        beam = self.load('spells--far-beam.json')
        self.assertEqual([b['type'] for b in beam['content']], ['fields', 'paragraph'])
        self.assertEqual([i['label'] for i in beam['content'][0]['items']], ['CN', 'Range', 'Target', 'Duration'])
        self.assertEqual(beam['content'][1]['text'], 'Your beam reaches a ship at sea.')
        self.assertEqual(self.load('keeper-spells.json')['content'][0]['text'], 'Every keeper learns these first.')

        self.assertEqual([x['entry'] for x in report['field_lines_joined']], ['Far Beam'])
        self.assertEqual([x['entry'] for x in report['labels_not_bold']], ['Calm Sea'])
        self.assertIn('Prayers of the Keeper', report['left_out'])        # "entry": false
        cov = run('check_coverage.py', self.layout, self.out)
        self.assertEqual(cov.returncode, 0, cov.stdout)

    def test_a_heading_at_spell_level_without_fields_is_an_error(self):
        r, report = self.convert(stray=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("'Oil Store'" in e['error'] for e in report['errors']), report['errors'])

    def test_a_petty_spell_without_cn_is_an_error(self):
        plan = dict(PLAN, lists=[dict(PLAN['lists'][0]), dict(PLAN['lists'][1], kind='petty')])
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        r, report = self.convert()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any(e['error'].startswith('Calm Sea') and 'cn' in e['error'] for e in report['errors']),
                        report['errors'])


if __name__ == '__main__':
    unittest.main()
