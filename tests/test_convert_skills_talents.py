"""Tests for convert_skills_talents.py, and the layout and text rules it relies on, on an invented
two-page skills-and-talents chapter the test draws itself: no book text.

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
    'source': 'TEST', 'chapter': 'ch4',
    'skills': {'pages': [1, 1], 'section': 'Keeper Skill List'},
    'talents': {'pages': [2, 2], 'section': 'Keeper Talent List'},
    'entries': [
        {'name': 'Keeper Skills', 'page': 1, 'kind': 'procedure'},
        {'name': 'Keeper Talents', 'page': 2, 'kind': 'procedure'},
    ],
    'text_tables': [{'page': 2, 'header': 'Wicks Owned Oil Cost', 'columns': ['Wicks Owned', 'Oil Cost'],
                     'rows': 2, 'title': 'Oil Costs'}],
}

LEFT, RIGHT = 50, 306


def draw_chapter(path, stray=False):
    """Page 1: a quote sharing its baseline with a heading across the gutter; three skills with
    run-in headings ("Name (Char) kind" in two sizes), one grouped with a "Specialisations:" line
    over two lines, one grouped without, the last running on into page 2. Page 2: two talents
    with Max/Tests lines (one Tests line wrapping), the second with a situation and a small
    unruled table."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    def head(x, y, name, rest):
        text(x, y, name, 'Helvetica-Bold', 12)
        text(x + c.stringWidth(name, 'Helvetica-Bold', 12) + 3, y, rest, 'Helvetica-BoldOblique', 9)

    def label(x, y, lab, rest):
        text(x, y, lab, 'Helvetica-Bold')
        text(x + c.stringWidth(lab, 'Helvetica-Bold', 9) + 3, y, rest)

    y = h - 80
    text(LEFT, y, '‘Light the lamps, keeper, the', 'Helvetica-Oblique', 10)  # a quote, left column...
    text(RIGHT, y, 'Keeper Skills', 'Helvetica-Bold', 18)               # ...and a heading, right
    text(LEFT, y - 12, 'boats are coming in.’', 'Helvetica-Oblique', 10)
    for k in range(20):                      # the left column's body, so the gutter is found
        text(LEFT, y - 30 - 11 * k, 'Keepers keep the lamps burning.')
    y -= 20
    for s in ('Keepers learn their skills on the tower', 'stairs, a step at a time.'):
        text(RIGHT, y, s); y -= 11
    y -= 8
    head(RIGHT, y, 'Wick Lore', '(Int) advanced, grouped'); y -= 13
    for s in ('You know the kinds of wick and which', 'burns longest in a gale.'):
        text(RIGHT, y, s); y -= 11
    y -= 4
    label(RIGHT, y, 'Specialisations:', 'Cotton, Hemp, Rush,'); y -= 11
    text(RIGHT, y, 'Tallow'); y -= 15
    head(RIGHT, y, 'Signal', '(Fel) basic, grouped'); y -= 13
    text(RIGHT, y, 'You send signals with the great lamp.'); y -= 15
    if stray:
        text(RIGHT, y, 'Lamp Oil', 'Helvetica-Bold', 12); y -= 13
        text(RIGHT, y, 'A heading at skill level that is no skill.'); y -= 15
    head(RIGHT, y, 'Climb Stairs', '(T) basic'); y -= 13
    for s in ('You climb the tower stairs without', 'tiring, and carry oil while you'):
        text(RIGHT, y, s); y -= 11
    c.showPage()

    y = h - 80
    text(LEFT, y, 'climb, if the GM agrees.'); y -= 20                   # runs on from page 1
    text(LEFT, y, 'Keeper Talents', 'Helvetica-Bold', 18); y -= 20
    text(LEFT, y, 'Talents are a keeper’s tricks.'); y -= 20
    text(LEFT, y, 'Steady Hand', 'Helvetica-Bold', 12); y -= 13
    label(LEFT, y, 'Max:', 'Dexterity Bonus'); y -= 11
    label(LEFT, y, 'Tests:', 'Wick Lore when trimming wicks in'); y -= 11
    text(LEFT, y, 'the dark'); y -= 11
    for s in ('Your hand never shakes on the', 'ladder.'):
        text(LEFT, y, s); y -= 11
    y -= 6
    text(LEFT, y, 'Lamp Sense (Weather)', 'Helvetica-Bold', 12); y -= 13
    label(LEFT, y, 'Max:', '1'); y -= 11
    text(LEFT, y, 'You know when to light the lamps.'); y -= 13
    text(LEFT, y, 'Wicks Owned Oil Cost', 'Helvetica-Bold'); y -= 11
    for a, b in (('Up to 2', '10 pennies'), ('Up to 4', '20 pennies')):
        text(LEFT + 10, y, a)
        text(LEFT + 120, y, b)
        y -= 11
    text(LEFT, y, 'Oil is dear in winter.'); y -= 11
    for k in range(12):
        text(RIGHT, h - 80 - 11 * k, 'Fog rolls in over the harbour.')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class ConvertSkillsTalentsTest(unittest.TestCase):
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
        r = run('pdf_layout.py', pdf, '--pages', '1-2', '--out', self.layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.out = os.path.join(self.d, 'out')
        r = run('convert_skills_talents.py', self.layout, '--plan', os.path.join(self.d, 'plan.json'),
                '--out', self.out)
        with open(os.path.join(self.out, '_report.json')) as f:
            return r, json.load(f)

    def load(self, name):
        with open(os.path.join(self.out, name)) as f:
            return json.load(f)

    def test_layout_run_in_heading_and_a_shared_baseline(self):
        pdf = os.path.join(self.d, 'chapter.pdf')
        draw_chapter(pdf)
        layout = os.path.join(self.d, 'layout.json')
        run('pdf_layout.py', pdf, '--pages', '1-2', '--out', layout)
        with open(layout) as f:
            by = {l['text']: l for l in json.load(f)['lines']}
        self.assertIn('heading', by['Wick Lore (Int) advanced, grouped'])          # set by its lead
        self.assertEqual(by['Wick Lore (Int) advanced, grouped']['size'], 12.0)
        self.assertEqual(by['Keeper Skills']['column'], 'right')                  # not joined to the quote
        self.assertEqual(by['‘Light the lamps, keeper, the']['column'], 'left')

    def test_skills_and_talents(self):
        r, report = self.convert()
        self.assertEqual(r.returncode, 0, report['errors'])
        rec = {(x['_category'], x['slug']): x for x in self.load('_records.json')}
        self.assertEqual(set(rec), {('rules', 'keeper-skills'), ('rules', 'keeper-talents'),
                                    ('skills', 'wick-lore'), ('skills', 'climb-stairs'), ('skills', 'signal'),
                                    ('talents', 'steady-hand'), ('talents', 'lamp-sense')})
        self.assertEqual(rec[('skills', 'wick-lore')]['characteristic'], 'Int')
        self.assertEqual((rec[('skills', 'wick-lore')]['advanced'], rec[('skills', 'wick-lore')]['grouped']),
                         (True, True))
        self.assertEqual(rec[('skills', 'climb-stairs')]['section'], 'Keeper Skill List')
        self.assertEqual(rec[('talents', 'steady-hand')]['tests'], 'Wick Lore when trimming wicks in the dark')
        self.assertNotIn('tests', rec[('talents', 'lamp-sense')])

        lore = self.load('skills--wick-lore.json')
        self.assertEqual(lore['fields']['specialisations'], ['Cotton', 'Hemp', 'Rush', 'Tallow'])
        self.assertEqual(lore['content'][-1]['type'], 'fields')
        climb = self.load('skills--climb-stairs.json')
        self.assertIn('carry oil while you climb, if the GM agrees.', climb['content'][0]['text'])  # ran on
        self.assertEqual(report['questions'][0]['kind'], 'no-specialisations')   # Signal: grouped, no line

        hand = self.load('talents--steady-hand.json')
        self.assertEqual(hand['fields'], {'max': 'Dexterity Bonus', 'tests': 'Wick Lore when trimming wicks in the dark'})
        self.assertEqual([b['type'] for b in hand['content']], ['fields', 'paragraph'])
        self.assertEqual([i['label'] for i in hand['content'][0]['items']], ['Max', 'Tests'])
        self.assertEqual(hand['content'][1]['text'], 'Your hand never shakes on the ladder.')
        self.assertEqual(report['field_lines_joined'][0]['entry'], 'Steady Hand')

        sense = self.load('talents--lamp-sense.json')
        self.assertEqual(sense['name'], 'Lamp Sense')
        self.assertEqual(sense['fields'], {'situation': 'Weather', 'max': '1'})
        k = next(i for i, b in enumerate(sense['content']) if b['type'] == 'table')
        table = sense['content'][k]
        self.assertEqual(table['rows'], [['Up to 2', '10 pennies'], ['Up to 4', '20 pennies']])
        self.assertEqual(table['data'][0], {'wicks_owned': 'Up to 2', 'oil_cost': '10 pennies'})
        self.assertEqual(sense['content'][k + 1]['text'], 'Oil is dear in winter.')

        cov = run('check_coverage.py', self.layout, self.out)
        self.assertEqual(cov.returncode, 0, cov.stdout)

    def test_a_heading_at_skill_level_that_is_no_skill_is_an_error(self):
        r, report = self.convert(stray=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("'Lamp Oil'" in e['error'] for e in report['errors']), report['errors'])

    def test_a_text_table_row_without_a_gap_is_an_error(self):
        plan = dict(PLAN, text_tables=[dict(PLAN['text_tables'][0], rows=3)])   # takes in a prose line
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        r, report = self.convert()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any('is not a row of it' in e['error'] for e in report['errors']), report['errors'])


if __name__ == '__main__':
    unittest.main()
