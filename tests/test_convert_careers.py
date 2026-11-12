"""Tests for convert_careers.py on an invented career page the test draws itself (no book text).

The page copies the shape of a two-column career page: a title and species line, a
description, a quote in the right column, an advance scheme whose icons are a glyph (level
1) and three drawn shapes (levels 2-4), and a career path whose levels carry the same icons.

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
    HAVE_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAVE_REPORTLAB = False

COLS = ['WS', 'BS', 'S', 'T', 'I', 'Agi', 'Dex', 'Int', 'WP', 'Fel']
PLAN = {
    'source': 'TEST', 'chapter': 'ch3',
    'level_icons': {'1': {'mark_font': 'ZapfDingbats'}, '2': {'pts': 3}, '3': {'pts': 4}, '4': {'pts': 6}},
    'scheme_columns': {'ws': 'WS', 'bs': 'BS', 's': 'S', 't': 'T', 'i': 'I', 'agi': 'Ag', 'dex': 'Dex',
                       'int': 'Int', 'wp': 'WP', 'fel': 'Fel'},
    'careers': [{'name': 'Lamp Warden', 'page': 1, 'class': 'Burghers'}],
}
# level -> (title, status, skills, talents, trappings); "|" splits a list over two printed lines
LEVELS = [
    ('Wick Boy', 'Brass 2', 'Climb, Endurance, Gossip, |Melee (Basic), Perception', 'Night Vision, Sure-|footed',
     'Ladder, Taper'),
    ('Lamplighter', 'Brass 4', 'Cool, Haggle', 'Hardy, Tinker', 'Oil Flask'),
    ('Lamp Warden', 'Silver 1', 'Leadership, Lore (Wicks)', 'Menacing, Robust', 'Keys'),
    ('Keeper of Flames', 'Silver 3', 'Charm, Intuition', 'Stout-hearted, Savvy', 'Brass Lantern'),
]
SCHEME = {'WS': 1, 'T': 1, 'Fel': 1, 'Dex': 2, 'S': 3, 'WP': 4}     # characteristic -> level


def draw_career(path, swap_icons=False, missing_level=False, earning_italic=True):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFont('Helvetica', 7)
    c.drawString(w / 2 - 40, h - 25, 'THE LANTERN BOOK')
    c.drawString(w / 2, 20, '1')

    def icon(level, x, y):
        if swap_icons and level in (2, 3):
            level = 5 - level
        if level == 1:
            c.setFont('ZapfDingbats', 7)
            c.drawString(x, y, 'n')
            return
        p = c.beginPath()
        if level == 2:
            p.moveTo(x, y); p.curveTo(x + 2, y + 4, x + 4, y + 4, x + 6, y); p.curveTo(x + 4, y - 4, x + 2, y - 4, x, y)
        elif level == 3:
            p.moveTo(x, y); p.lineTo(x + 6, y); p.lineTo(x + 3, y + 6); p.close()
        else:
            p.moveTo(x, y); p.lineTo(x + 6, y); p.lineTo(x + 7, y + 4); p.lineTo(x + 3, y + 7); p.lineTo(x - 1, y + 4)
            p.close()
        c.drawPath(p, fill=1, stroke=0)

    def text(x, y, s, font='Helvetica', size=9, slant=False):
        t = c.beginText()
        t.setFont(font, size)
        t.setTextTransform(1, 0, 0.25 if slant else 0, 1, x, y)
        t.textOut(s)
        c.drawText(t)
        return x + c.stringWidth(s, font, size)

    y = h - 70
    text(50, y, 'Lamp Warden', 'Helvetica-Bold', 19)
    text(50, y - 14, 'Dwarf, Halfling, Human')
    body = ['Lamp Wardens keep the harbour lights burning', 'through fog and storm, climbing towers at',
            'dusk and dawn with oil and wick.', '', 'The best of them are trusted with the great',
            'beacon, and some say they never sleep.']
    yy = y - 40
    for s in body:
        if s:
            text(50, yy, s)
        yy -= 11 if s else 8
    quote = ['‘Mind the oil, lad, and the oil', 'will mind you.’', '– Old Hanne, Keeper of Flames',
             '', 'Wardens move between ports when a tower', 'falls dark for good.']
    yy = y - 40
    for s in quote:
        if s:
            text(320, yy, s, slant=s.startswith('‘') or s.startswith('will'))
        yy -= 11 if s else 8

    sy = y - 140
    text(110, sy, 'Lamp Warden Advance Scheme', 'Helvetica-Bold', 10)
    xs = [64 + i * 24 for i in range(len(COLS))]
    for x, col in zip(xs, COLS):
        text(x, sy - 16, col, 'Helvetica-Bold', 10)
    for col, lv in SCHEME.items():
        code = {'Ag': 'Agi'}.get(col, col)
        icon(lv, xs[COLS.index(code)] + 2, sy - 32)

    py = sy - 60
    text(65, py, 'Career Path', 'Helvetica-Bold', 18)
    py -= 22
    for n, (title, status, skills, talents, trappings) in enumerate(LEVELS, 1):
        if missing_level and n == 3:
            continue
        icon(n, 55, py + 1)
        text(65, py, f'{title} — {status}', 'Helvetica-Bold')
        py -= 11
        for label, val in (('Skills:', skills), ('Talents:', talents), ('Trappings:', trappings)):
            parts = val.split('|')
            x = text(65, py, label, 'Helvetica-Bold')
            for k, part in enumerate(parts):
                if k:
                    py -= 11
                    x = 65
                if 'Melee (Basic)' in part:      # one item set in italics by slanting the roman font
                    before, after = part.split('Melee (Basic)')
                    x = text(x + 3, py, before) if before else x + 3
                    x = text(x, py, 'Melee (Basic)', slant=earning_italic)
                    text(x, py, after)
                else:
                    text(x + 3 if k == 0 else x, py, part)
            py -= 11
        py -= 6
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_REPORTLAB, 'reportlab is needed to draw the fixture PDF')
class ConvertCareersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(PLAN, f)

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, **draw):
        pdf = os.path.join(self.d, 'page.pdf')
        draw_career(pdf, **draw)
        layout = os.path.join(self.d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--icon-fonts', 'ZapfDingbats', '--out', layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(self.d, 'out')
        r = run('convert_careers.py', layout, '--plan', os.path.join(self.d, 'plan.json'), '--out', out)
        with open(os.path.join(out, '_report.json')) as f:
            report = json.load(f)
        return r, out, layout, report

    def test_reads_the_scheme_and_the_career_path(self):
        r, out, layout, report = self.convert()
        self.assertEqual(r.returncode, 0, report['errors'])
        with open(os.path.join(out, 'lamp-warden.json')) as f:
            e = json.load(f)
        f = e['fields']
        self.assertEqual(f['class'], 'Burghers')
        self.assertEqual(f['species'], ['Dwarf', 'Halfling', 'Human'])
        self.assertEqual(f['levels'], ['Wick Boy', 'Lamplighter', 'Lamp Warden', 'Keeper of Flames'])
        self.assertEqual(f['status'], ['Brass 2', 'Brass 4', 'Silver 1', 'Silver 3'])
        self.assertEqual([f['advances'][k]['characteristics'] for k in '1234'],
                         [['WS', 'T', 'Fel'], ['Dex'], ['S'], ['WP']])
        self.assertEqual(f['advances']['1']['skills'],
                         ['Climb', 'Endurance', 'Gossip', 'Melee (Basic)', 'Perception'])
        self.assertEqual(f['advances']['1']['talents'], ['Night Vision', 'Sure-footed'])   # joined over the line end
        block = e['content'][-1]
        self.assertEqual(block['type'], 'career_levels')
        self.assertIn('*Melee (Basic)*', block['levels'][0]['skills'])                    # italics kept as printed
        self.assertEqual(f['earning_skill'], 'Melee (Basic)')        # the level 1 skill in italics
        self.assertEqual(e['content'][0], {'type': 'paragraph', 'text': 'Dwarf, Halfling, Human'})
        paras = [b['text'] for b in e['content'] if b['type'] == 'paragraph']
        self.assertTrue(paras[1].startswith('Lamp Wardens keep') and paras[1].endswith('oil and wick.'))
        self.assertTrue(paras[3].startswith('*‘Mind the oil'))                            # right column after left
        kinds = {q['kind'] for q in report['questions']}
        self.assertEqual(kinds, {'hyphen-join'})
        with open(os.path.join(out, '_records.json')) as fh:
            rec = json.load(fh)
        self.assertEqual(rec[0]['slug'], 'lamp-warden')
        self.assertEqual(rec[0]['page'], 1)
        self.assertEqual(rec[0]['earning_skill'], 'Melee (Basic)')
        with open(os.path.join(out, 'lamp-warden.md')) as fh:
            self.assertIn('| 2 | Lamplighter | Brass 4 | Dex |', fh.read())
        cov = run('check_coverage.py', layout, out)
        self.assertEqual(cov.returncode, 0, cov.stdout)

    def test_a_level_icon_that_does_not_match_its_level_is_an_error(self):
        r, out, layout, report = self.convert(swap_icons=True)
        self.assertEqual(r.returncode, 1)
        errors = [e['error'] for e in report['errors']]
        self.assertIn("level 2 line 'Lamplighter' has the icon of level 3", errors)

    def test_no_skill_in_italics_at_level_1_is_an_error(self):
        r, out, layout, report = self.convert(earning_italic=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn('0 level 1 skills in italics (the skill for Earning money), not 1',
                      [e['error'] for e in report['errors']])

    def test_a_missing_level_is_an_error(self):
        r, out, layout, report = self.convert(missing_level=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn('3 career levels, not 4', [e['error'] for e in report['errors']])

    def test_a_career_not_on_its_page_is_an_error(self):
        plan = dict(PLAN, careers=[{'name': 'Fog Keeper', 'page': 1, 'class': 'Burghers'}])
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        r, out, layout, report = self.convert()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no heading 'Fog Keeper' on page 1", [e['error'] for e in report['errors']])


if __name__ == '__main__':
    unittest.main()
