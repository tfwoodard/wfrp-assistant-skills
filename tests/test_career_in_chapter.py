"""Tests for a career printed inside a chapter of prose, on invented pages the test draws itself.

Page 1: the chapter's title, a rules section, then a career: its heading, species line and
description, and a panel holding its advance scheme and career path. Page 2: a section about the
career, a sidebar, and the next rules section.

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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import convert_rules  # noqa: E402
from test_convert_careers import COLS, LEVELS, PLAN as CAREER_PLAN, SCHEME  # noqa: E402

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {
    'source': 'TEST', 'chapter': 'ch3',
    'level_icons': CAREER_PLAN['level_icons'],
    'scheme_columns': dict(CAREER_PLAN['scheme_columns'], ag='Ag'),      # two labels, one column
    'entries': [
        {'name': 'Tower Trades', 'page': 1, 'kind': 'procedure'},
        {'name': 'Lamp Warden', 'page': 1, 'career': {'class': 'Burghers'}},
        {'name': 'Beacon Law', 'page': 2, 'kind': 'procedure'},
    ],
}


def draw_pages(path):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    panel = ImageReader(Image.new('RGB', (40, 40), (230, 220, 190)))

    def text(x, y, s, font='Helvetica', size=9, slant=False):
        t = c.beginText()
        t.setFont(font, size)
        t.setTextTransform(1, 0, 0.25 if slant else 0, 1, x, y)
        t.textOut(s)
        c.drawText(t)
        return x + c.stringWidth(s, font, size)

    def icon(level, x, y):
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

    def body(x, y, lines):
        for s in lines:
            text(x, y, s)
            y -= 11
        return y

    # Page 1
    text(150, h - 70, 'THE LANTERN TRADES', 'Helvetica-Bold', 30)
    text(50, h - 110, 'Tower Trades', 'Helvetica-Bold', 19)
    body(50, h - 126, ['Every tower keeps a warden and a boy', 'to carry the oil up the stair.'])
    y = h - 180
    text(50, y, 'Lamp Warden', 'Helvetica-Bold', 19)
    text(50, y - 14, 'Dwarf, Halfling, Human')
    body(50, y - 34, ['Lamp Wardens keep the harbour lights burning', 'through fog and storm, with oil and wick.'])
    body(320, y - 34, ['Wardens move between ports when a tower', 'falls dark for good.'])
    sy = y - 80
    c.drawImage(panel, 44, sy - 290, 250, 304)
    text(100, sy, 'Lamp Warden Advance Scheme', 'Helvetica-Bold', 10)
    xs = [56 + i * 23 for i in range(len(COLS))]
    for x, col in zip(xs, COLS):
        text(x, sy - 16, 'Ag' if col == 'Agi' else col, 'Helvetica-Bold', 10)
    for col, lv in SCHEME.items():
        icon(lv, xs[COLS.index(col)] + 2, sy - 32)
    py = sy - 60
    text(65, py, 'Career Path', 'Helvetica-Bold', 18)
    py -= 22
    for n, (title, status, skills, talents, trappings) in enumerate(LEVELS, 1):
        icon(n, 55, py + 1)
        text(65, py, f'{title} — {status}', 'Helvetica-Bold')
        py -= 11
        for label, val in (('Skills:', skills), ('Talents:', talents), ('Trappings:', trappings)):
            x = text(65, py, label, 'Helvetica-Bold')
            for k, part in enumerate(val.split('|')):
                if k:
                    py -= 11
                    x = 65
                if 'Melee (Basic)' in part:
                    before, after = part.split('Melee (Basic)')
                    x = text(x + 3, py, before) if before else x + 3
                    x = text(x, py, 'Melee (Basic)', slant=True)
                    text(x, py, after)
                else:
                    text(x + 3 if k == 0 else x, py, part)
            py -= 11
        py -= 6
    c.drawString(w / 2, 20, '1')
    c.showPage()
    # Page 2
    text(50, h - 80, 'Night Rounds', 'Helvetica-Bold', 14)
    body(50, h - 96, ['A warden walks the gallery twice each night', 'and counts the ships that pass below.'])
    c.drawImage(panel, 310, h - 190, 230, 120)
    text(320, h - 90, 'The Dark Tower', 'Helvetica-Bold', 12)
    body(320, h - 106, ['No warden will take the north tower since', 'its lamp went out by itself.'])
    text(50, h - 240, 'Beacon Law', 'Helvetica-Bold', 19)
    body(50, h - 256, ['A lit beacon may not be dimmed before dawn.'])
    c.setFont('Helvetica', 9)
    c.drawString(w / 2, 20, '2')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class CareerInChapterTest(unittest.TestCase):
    def convert(self, d, taken=(), plan=PLAN):
        pdf, layout, planf, out = (os.path.join(d, n) for n in ('pages.pdf', 'layout.json', 'plan.json', 'out'))
        draw_pages(pdf)
        r = run('pdf_layout.py', pdf, '--pages', '1-2', '--boxes', '--icon-fonts', 'ZapfDingbats', '--out', layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(planf, 'w', encoding='utf-8') as f:
            json.dump(plan, f)
        args = [a for cat, slugs in taken for a in ('--taken', f'{cat}={self.index(d, cat, slugs)}')]
        r = run('convert_rules.py', layout, '--plan', planf, '--out', out, *args)
        with open(os.path.join(out, '_report.json'), encoding='utf-8') as f:
            report = json.load(f)
        self.assertEqual(report['errors'], [], r.stdout)
        with open(os.path.join(out, '_records.json'), encoding='utf-8') as f:
            records = json.load(f)
        return out, layout, report, records

    def index(self, d, cat, slugs):
        path = os.path.join(d, f'{cat}-index.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([{'slug': s, 'source': 'OLD'} for s in slugs], f)
        return path

    def test_the_career_is_read_from_its_panel_and_keeps_its_prose(self):
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, records = self.convert(d)
            with open(os.path.join(out, 'careers--lamp-warden.json'), encoding='utf-8') as f:
                e = json.load(f)
            f = e['fields']
            self.assertEqual(f['class'], 'Burghers')
            self.assertEqual(f['species'], ['Dwarf', 'Halfling', 'Human'])
            self.assertEqual(f['levels'], [l[0] for l in LEVELS])
            self.assertEqual(f['status'], [l[1] for l in LEVELS])
            self.assertEqual(f['earning_skill'], 'Melee (Basic)')
            self.assertEqual(f['advances']['1']['characteristics'], ['WS', 'T', 'Fel'])
            kinds = [b['type'] for b in e['content']]
            self.assertEqual(kinds, ['paragraph', 'paragraph', 'paragraph', 'career_levels', 'heading',
                                     'paragraph', 'sidebar'])
            self.assertEqual(e['content'][0]['text'], 'Dwarf, Halfling, Human')
            self.assertEqual(e['content'][4]['text'], 'Night Rounds')
            self.assertEqual(e['content'][6]['title'], 'The Dark Tower')
            rec = next(r for r in records if r['slug'] == 'lamp-warden')
            self.assertEqual(rec['_category'], 'careers')
            self.assertNotIn('advances', rec)
            self.assertEqual(rec['earning_skill'], 'Melee (Basic)')
            self.assertEqual(sorted((r['_category'], r['slug']) for r in records),
                             [('careers', 'lamp-warden'), ('rules', 'beacon-law'), ('rules', 'tower-trades')])
            r = run('check_coverage.py', layout, out)
            self.assertIn('every word', r.stdout, r.stdout + r.stderr)

    def test_a_slug_is_taken_only_within_its_category(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, report, records = self.convert(d, taken=[('rules', ['lamp-warden']), ('careers', ['beacon-law'])])
            self.assertEqual(sorted(r['slug'] for r in records), ['beacon-law', 'lamp-warden', 'tower-trades'])
            self.assertNotIn('same_name', report)
        with tempfile.TemporaryDirectory() as d:
            _, _, report, records = self.convert(d, taken=[('careers', ['lamp-warden']), ('rules', ['beacon-law'])])
            self.assertEqual(sorted(r['slug'] for r in records), ['beacon-law-test', 'lamp-warden-test', 'tower-trades'])
            self.assertEqual(report['same_name'], [
                {'category': 'careers', 'name': 'Lamp Warden', 'taken': 'lamp-warden'},
                {'category': 'rules', 'name': 'Beacon Law', 'taken': 'beacon-law'}])

    def test_a_career_without_its_class_or_icons_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, layout, planf, out = (os.path.join(d, n) for n in ('pages.pdf', 'layout.json', 'plan.json', 'out'))
            draw_pages(pdf)
            run('pdf_layout.py', pdf, '--pages', '1-2', '--boxes', '--icon-fonts', 'ZapfDingbats', '--out', layout)
            plan = {k: v for k, v in PLAN.items() if k != 'level_icons'}
            with open(planf, 'w', encoding='utf-8') as f:
                json.dump(plan, f)
            r = run('convert_rules.py', layout, '--plan', planf, '--out', out)
            self.assertEqual(r.returncode, 1)
            with open(os.path.join(out, '_report.json'), encoding='utf-8') as f:
                self.assertIn('level_icons', json.dumps(json.load(f)['errors']))


class GroupBandTest(unittest.TestCase):
    def test_a_band_in_capitals_heads_the_rows_below_it_in_a_two_column_table(self):
        region = {'id': '1.1', 'page': 1, 'columns': ['Tower', 'Keeper'],
                  'rows': [['', 'NORTH SHORE'], ['Gull Rock', 'Hanne'], ['SOUTH SHORE', ''], ['Seal Point', 'Odo']]}
        report = {'tables_to_confirm': [], 'errors': [], 'questions': []}
        block = convert_rules.table_block(region, 'Towers', {}, report, 'Towers')
        self.assertEqual(block['rows'], [['Gull Rock', 'Hanne'], ['Seal Point', 'Odo']])
        self.assertEqual(block['groups'], [{'before': 0, 'text': 'North Shore'}, {'before': 1, 'text': 'South Shore'}])
        self.assertEqual([r['tower'] for r in block['data']], ['Gull Rock', 'Seal Point'])


if __name__ == '__main__':
    unittest.main()
