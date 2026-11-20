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

FIFTH_COLUMN = next(c for c in COLS if c not in SCHEME)

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


LETTERS = 'QRSTU'
FIFTH = ('Lamp Marshal', 'Gold 2', 'Lore (Oil), Leadership', 'Iron Will', 'Seal of the Harbour')


def draw_pages(path, bare=False, letters=False, plain_skills=False, fifth=False, first=1, scheme='Lamp Warden',
               no_dash=0):
    """`bare`: a career printed with no species line and, in its levels, no status, trappings or
    italic skill (a lamp sprite's). `letters`: the levels of the career path are marked with a
    glyph that reads as a letter, not with the scheme's icon. `plain_skills`: no skill is in italics.
    `fifth`: the career has a fifth level, its icon a six-sided shape, advancing Int.
    `first`: the career is entered part-way, and prints only the levels from there.
    `scheme`: the name in the advance scheme's title, where it shortens the career's.
    `no_dash`: the level whose line is printed without its dash."""
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
        elif level == 4:
            p.moveTo(x, y); p.lineTo(x + 6, y); p.lineTo(x + 7, y + 4); p.lineTo(x + 3, y + 7); p.lineTo(x - 1, y + 4)
            p.close()
        else:
            p.moveTo(x, y); p.lineTo(x + 2, y - 2); p.lineTo(x + 5, y - 2); p.lineTo(x + 7, y); p.lineTo(x + 7, y + 3)
            p.lineTo(x + 3, y + 6); p.lineTo(x - 1, y + 3)
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
    if not bare:
        text(50, y - 14, 'Dwarf, Halfling, Human')
    body(50, y - 34, ['Lamp Wardens keep the harbour lights burning', 'through fog and storm, with oil and wick.'])
    body(320, y - 34, ['Wardens move between ports when a tower', 'falls dark for good.'])
    sy = y - 80
    c.drawImage(panel, 44, sy - (350 if fifth else 290), 250, 364 if fifth else 304)
    text(100, sy, f'{scheme} Advance Scheme', 'Helvetica-Bold', 10)
    xs = [56 + i * 23 for i in range(len(COLS))]
    for x, col in zip(xs, COLS):
        text(x, sy - 16, 'Ag' if col == 'Agi' else col, 'Helvetica-Bold', 10)
    for col, lv in dict(SCHEME, **({FIFTH_COLUMN: 5} if fifth else {})).items():
        if lv >= first:
            icon(lv, xs[COLS.index(col)] + 2, sy - 32)
    py = sy - 60
    text(65, py, 'Career Path', 'Helvetica-Bold', 18)
    py -= 22
    for n, (title, status, skills, talents, trappings) in enumerate(LEVELS + ([FIFTH] if fifth else []), 1):
        if n < first:
            continue
        if letters:
            text(55, py, LETTERS[n - 1])
        else:
            icon(n, 55, py + 1)
        text(65, py, title if bare else f'{title} {status}' if n == no_dash else f'{title} — {status}', 'Helvetica-Bold')
        py -= 11
        for label, val in (('Skills:', skills), ('Talents:', talents), ('Trappings:', trappings))[:2 if bare else 3]:
            x = text(65, py, label, 'Helvetica-Bold')
            for k, part in enumerate(val.split('|')):
                if k:
                    py -= 11
                    x = 65
                if 'Melee (Basic)' in part and not bare and not plain_skills:
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
    def convert(self, d, taken=(), plan=PLAN, bare=False, errors=(), **drawn):
        pdf, layout, planf, out = (os.path.join(d, n) for n in ('pages.pdf', 'layout.json', 'plan.json', 'out'))
        draw_pages(pdf, bare, **drawn)
        r = run('pdf_layout.py', pdf, '--pages', '1-2', '--boxes', '--icon-fonts', 'ZapfDingbats', '--out', layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(planf, 'w', encoding='utf-8') as f:
            json.dump(plan, f)
        args = [a for cat, slugs in taken for a in ('--taken', f'{cat}={self.index(d, cat, slugs)}')]
        r = run('convert_rules.py', layout, '--plan', planf, '--out', out, *args)
        with open(os.path.join(out, '_report.json'), encoding='utf-8') as f:
            report = json.load(f)
        self.assertEqual([e['error'] for e in report['errors']], list(errors), r.stdout)
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

    def test_a_bare_career_has_no_species_line_status_trappings_or_earning_skill(self):
        entries = [dict(e, career={'class': 'Burghers', 'bare': True, 'species': ['Lamp Sprite']})
                   if e.get('career') else e for e in PLAN['entries']]
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, records = self.convert(d, plan=dict(PLAN, entries=entries), bare=True)
            with open(os.path.join(out, 'careers--lamp-warden.json'), encoding='utf-8') as f:
                e = json.load(f)
            f = e['fields']
            self.assertEqual((f['class'], f['species']), ('Burghers', ['Lamp Sprite']))
            self.assertEqual(f['levels'], [l[0] for l in LEVELS])
            self.assertNotIn('status', f)
            self.assertNotIn('earning_skill', f)
            self.assertEqual(sorted(f['advances']['1']), ['characteristics', 'skills', 'talents'])
            levels = next(b for b in e['content'] if b['type'] == 'career_levels')['levels']
            self.assertEqual(sorted(levels[0]), ['characteristics', 'skills', 'talents', 'title'])
            self.assertEqual([b['type'] for b in e['content']][:3], ['paragraph', 'paragraph', 'career_levels'])
            with open(os.path.join(out, 'careers--lamp-warden.md'), encoding='utf-8') as f:
                md = f.read()
            self.assertIn('| Level | Title | Characteristics |', md)
            self.assertIn(f'***{LEVELS[0][0]}***\n', md)
            r = run('check_coverage.py', layout, out)
            self.assertIn('every word', r.stdout, r.stdout + r.stderr)

    def test_levels_marked_with_a_glyph_that_reads_as_a_letter(self):
        icons = {lv: dict(spec, letter=LETTERS[int(lv) - 1]) for lv, spec in PLAN['level_icons'].items()}
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, _ = self.convert(d, plan=dict(PLAN, level_icons=icons), letters=True)
            with open(os.path.join(out, 'careers--lamp-warden.json'), encoding='utf-8') as f:
                f = json.load(f)['fields']
            self.assertEqual(f['levels'], [l[0] for l in LEVELS])           # the letter is no part of a title
            self.assertEqual(f['status'], [l[1] for l in LEVELS])
            self.assertEqual(f['advances']['1']['characteristics'], ['WS', 'T', 'Fel'])
            self.assertEqual([x for x in report['left_out'] if x in LETTERS], list(LETTERS[:4]))
            r = run('check_coverage.py', layout, out)
            self.assertIn('every word', r.stdout, r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as d:                             # a letter out of order is caught
            icons['2'], icons['3'] = dict(icons['2'], letter='S'), dict(icons['3'], letter='R')
            self.convert(d, plan=dict(PLAN, level_icons=icons), letters=True, errors=[
                f"level 2 line {LEVELS[1][0]!r} has the icon of level 3", f"level 3 line {LEVELS[2][0]!r} has the icon of level 2"])

    def test_a_career_with_a_fifth_level(self):
        icons = dict(PLAN['level_icons'], **{'5': {'pts': 8}})
        five = [dict(e, career={'class': 'Burghers', 'levels': 5}) if e.get('career') else e for e in PLAN['entries']]
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, _ = self.convert(d, plan=dict(PLAN, level_icons=icons, entries=five), fifth=True)
            with open(os.path.join(out, 'careers--lamp-warden.json'), encoding='utf-8') as f:
                f = json.load(f)['fields']
            self.assertEqual(f['levels'], [l[0] for l in LEVELS] + ['Lamp Marshal'])
            self.assertEqual(f['status'][-1], 'Gold 2')
            self.assertEqual(f['advances']['5']['characteristics'], [PLAN['scheme_columns'].get(FIFTH_COLUMN.lower(), FIFTH_COLUMN)])
            self.assertIn('every word', run('check_coverage.py', layout, out).stdout)
        with tempfile.TemporaryDirectory() as d:                             # five printed, the plan expects four
            self.convert(d, plan=dict(PLAN, level_icons=icons), fifth=True, errors=['5 career levels, not 4'])
        with tempfile.TemporaryDirectory() as d:                             # the plan expects five, four printed
            self.convert(d, plan=dict(PLAN, level_icons=icons, entries=five), errors=['4 career levels, not 5'])

    def test_a_career_entered_part_way(self):
        icons = dict(PLAN['level_icons'], **{'5': {'pts': 8}})
        late = {'class': 'Burghers', 'first_level': 3, 'levels': 3, 'earning_skill': False}
        entries = [dict(e, career=late) if e.get('career') else e for e in PLAN['entries']]
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, records = self.convert(d, plan=dict(PLAN, level_icons=icons, entries=entries),
                                                        fifth=True, first=3)
            with open(os.path.join(out, 'careers--lamp-warden.json'), encoding='utf-8') as f:
                entry = json.load(f)
            f = entry['fields']
            self.assertEqual(f['first_level'], 3)
            self.assertEqual(f['levels'], [l[0] for l in LEVELS[2:]] + ['Lamp Marshal'])
            self.assertEqual(sorted(f['advances']), ['3', '4', '5'])
            self.assertEqual(f['advances']['3']['characteristics'], [c for c, lv in SCHEME.items() if lv == 3])
            block = next(b for b in entry['content'] if b['type'] == 'career_levels')
            self.assertEqual(block['first_level'], 3)
            with open(os.path.join(out, 'careers--lamp-warden.md'), encoding='utf-8') as f:
                self.assertIn(f'| 3 | {LEVELS[2][0]} |', f.read())
            self.assertIn('every word', run('check_coverage.py', layout, out).stdout)
        with tempfile.TemporaryDirectory() as d:                             # the plan doesn't say so
            five = [dict(e, career={'class': 'Burghers', 'levels': 3, 'earning_skill': False}) if e.get('career') else e
                    for e in PLAN['entries']]
            self.convert(d, plan=dict(PLAN, level_icons=icons, entries=five), fifth=True, first=3, errors=[
                f"level 1 line {LEVELS[2][0]!r} has the icon of level 3", f"level 2 line {LEVELS[3][0]!r} has the icon of level 4",
                "level 3 line 'Lamp Marshal' has the icon of level 5"])

    def test_a_scheme_titled_with_a_shorter_name(self):
        with tempfile.TemporaryDirectory() as d:
            self.convert(d, scheme='Warden', errors=['no box holding its advance scheme'])
        entries = [dict(e, career={'class': 'Burghers', 'scheme': 'Warden'}) if e.get('career') else e
                   for e in PLAN['entries']]
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, records = self.convert(d, plan=dict(PLAN, entries=entries), scheme='Warden')
            self.assertEqual(next(r for r in records if r['slug'] == 'lamp-warden')['levels'], [l[0] for l in LEVELS])
            self.assertIn('Warden Advance Scheme', report['left_out'])
            self.assertIn('every word', run('check_coverage.py', layout, out).stdout)

    def test_a_level_line_printed_without_its_dash(self):
        with tempfile.TemporaryDirectory() as d:
            out, layout, report, records = self.convert(d, no_dash=3)
            career = next(r for r in records if r['slug'] == 'lamp-warden')
            self.assertEqual((career['levels'], career['status']), ([l[0] for l in LEVELS], [l[1] for l in LEVELS]))
            self.assertEqual([q['text'] for q in report['questions'] if q['kind'] == 'level-without-dash'],
                             [f"{LEVELS[2][0] + ' ' + LEVELS[2][1]!r}: read as a level line though it has no dash"])
            self.assertIn('every word', run('check_coverage.py', layout, out).stdout)

    def test_a_career_with_no_skill_in_italics(self):
        with tempfile.TemporaryDirectory() as d:
            self.convert(d, plain_skills=True, errors=[
                '0 level 1 skills in italics (the skill for Earning money), not 1'])
        entries = [dict(e, career={'class': 'Burghers', 'earning_skill': False}) if e.get('career') else e
                   for e in PLAN['entries']]
        with tempfile.TemporaryDirectory() as d:
            out, _, report, records = self.convert(d, plan=dict(PLAN, entries=entries), plain_skills=True)
            self.assertEqual(report['excused'], ['Lamp Warden: the plan says the book marks no skill for Earning money'])
            self.assertIsNone(next(r for r in records if r['slug'] == 'lamp-warden')['earning_skill'])
        with tempfile.TemporaryDirectory() as d:                             # the plan says none, the book has one
            self.convert(d, plan=dict(PLAN, entries=entries), errors=[
                '1 level 1 skills in italics (the skill for Earning money), not 0'])

    def test_a_slug_is_taken_only_within_its_category(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, report, records = self.convert(d, taken=[('rules', ['lamp-warden']), ('careers', ['beacon-law'])])
            self.assertEqual(sorted(r['slug'] for r in records), ['beacon-law', 'lamp-warden', 'tower-trades'])
            self.assertNotIn('same_name', report)
        with tempfile.TemporaryDirectory() as d:
            plan = dict(PLAN, relations={'careers/lamp-warden-test': [{'role': 'replaces', 'to': 'careers/lamp-warden'}],
                                         'rules/beacon-law-test': [{'role': 'adds-to', 'to': 'rules/beacon-law'}]})
            _, _, report, records = self.convert(d, taken=[('careers', ['lamp-warden']), ('rules', ['beacon-law'])],
                                                 plan=plan)
            self.assertEqual(sorted(r['slug'] for r in records), ['beacon-law-test', 'lamp-warden-test', 'tower-trades'])
            self.assertEqual(report['same_name'], [
                {'category': 'careers', 'name': 'Lamp Warden', 'taken': 'lamp-warden', 'relation': 'from the plan'},
                {'category': 'rules', 'name': 'Beacon Law', 'taken': 'beacon-law', 'relation': 'from the plan'}])

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
