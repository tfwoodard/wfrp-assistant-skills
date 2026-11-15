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


RITE_PLAN = {
    'source': 'TEST', 'chapter': 'ch8', 'entries': [],
    'lists': [{'name': 'Lamp Rites', 'page': 1, 'kind': 'ritual', 'not_spells': ['Old Rites']}],
}


def draw_rites(path):
    """A list of rites: a subheading at the rites' own size, then two rites whose fields run over
    several lines (one line holding two fields, one field's second line starting with a capital),
    a blank line, and the description. The second rite's fields end at the foot of the left
    column and its description starts the right."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)
        return x + c.stringWidth(s, font, size)

    def fields(x, y, rows):
        for row in rows:
            xx = x
            for lab, rest in row:
                if lab:
                    xx = text(xx, y, lab, 'Helvetica-Bold') + 3
                xx = text(xx, y, rest) + 6
            y -= 11
        return y

    y = h - 80
    text(LEFT, y, 'Lamp Rites', 'Helvetica-Bold', 18); y -= 18
    text(LEFT, y, 'Rites take a night and a keeper’s patience.'); y -= 20
    text(LEFT, y, 'Old Rites', 'Helvetica-Bold', 14); y -= 14
    text(LEFT, y, 'The oldest rites are sung, not spoken.'); y -= 20
    text(LEFT, y, 'Kindle the Great Lamp', 'Helvetica-Bold', 14); y -= 14
    y = fields(LEFT, y, [[('CN:', '12'), ('Type:', 'Lore of Lamps')], [('Learning XP:', '100')],
                         [('Ingredients:', 'A cask of whale oil and a new')], [('', 'Wick of braided flax.')],
                         [('Conditions:', 'A moonless night.')], [('Sacrifices:', 'None.')],
                         [('Consequences:', 'The lamp gutters.')]])
    y -= 11
    text(LEFT, y, 'The great lamp burns for a year and a day.'); y -= 20
    text(LEFT, y, 'Call the Fog', 'Helvetica-Bold', 14); y -= 14
    fields(LEFT, y, [[('CN:', 'The keeper’s age'), ('Type:', 'Any Lore')], [('Learning XP:', '250')],
                     [('Ingredients:', 'None.')], [('Conditions:', 'None.')], [('Sacrifices:', 'A night’s sleep.')],
                     [('Consequences:', 'The fog stays a week.')]])
    text(RIGHT, h - 80, 'Fog rolls in from the sea until dawn.')
    for k in range(1, 5):
        text(RIGHT, h - 80 - 11 * k, 'Gulls circle the tower all day.')
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


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class RitualsTest(unittest.TestCase):
    def test_rites_with_fields_over_several_lines(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, layout, planf, out = (os.path.join(d, n) for n in ('c.pdf', 'layout.json', 'plan.json', 'out'))
            draw_rites(pdf)
            self.assertEqual(run('pdf_layout.py', pdf, '--pages', '1', '--out', layout).returncode, 0)
            with open(planf, 'w') as f:
                json.dump(RITE_PLAN, f)
            r = run('convert_spells.py', layout, '--plan', planf, '--out', out)
            with open(os.path.join(out, '_report.json')) as f:
                report = json.load(f)
            self.assertEqual(report['errors'], [])
            with open(os.path.join(out, '_records.json')) as f:
                rec = {(x['_category'], x['slug']): x for x in json.load(f)}
            self.assertEqual(set(rec), {('rules', 'lamp-rites'), ('spells', 'kindle-the-great-lamp'),
                                        ('spells', 'call-the-fog')})
            lamp = rec[('spells', 'kindle-the-great-lamp')]
            self.assertEqual((lamp['kind'], lamp['lore'], lamp['cn'], lamp['type'], lamp['learning_xp'],
                              lamp['section']), ('ritual', 'Lamps', 12, 'Lore of Lamps', 100, 'Lamp Rites'))
            self.assertNotIn('range', lamp)
            fog = rec[('spells', 'call-the-fog')]
            self.assertEqual((fog['lore'], fog['cn'], fog['type']), (None, 'The keeper’s age', 'Any Lore'))
            with open(os.path.join(out, 'spells--kindle-the-great-lamp.json')) as f:
                e = json.load(f)
            self.assertEqual([b['type'] for b in e['content']], ['fields', 'paragraph'])
            self.assertEqual([(i['label'], i['text']) for i in e['content'][0]['items']], [
                ('CN', '12'), ('Type', 'Lore of Lamps'), ('Learning XP', '100'),
                ('Ingredients', 'A cask of whale oil and a new Wick of braided flax.'),
                ('Conditions', 'A moonless night.'), ('Sacrifices', 'None.'), ('Consequences', 'The lamp gutters.')])
            self.assertEqual(e['fields']['ingredients'], 'A cask of whale oil and a new Wick of braided flax.')
            self.assertEqual(e['content'][1]['text'], 'The great lamp burns for a year and a day.')
            with open(os.path.join(out, 'spells--call-the-fog.json')) as f:
                e = json.load(f)
            self.assertEqual(e['content'][0]['items'][-1], {'label': 'Consequences', 'text': 'The fog stays a week.'})
            self.assertTrue(e['content'][1]['text'].startswith('Fog rolls in from the sea until dawn.'))
            with open(os.path.join(out, 'lamp-rites.json')) as f:
                self.assertIn('Old Rites', [b.get('text') for b in json.load(f)['content']])
            self.assertEqual(run('check_coverage.py', layout, out).returncode, 0)

    def test_a_rite_missing_a_field_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, layout, planf, out = (os.path.join(d, n) for n in ('c.pdf', 'layout.json', 'plan.json', 'out'))
            draw_chapter(pdf)                      # spells, read as rites: no Type or Learning XP
            run('pdf_layout.py', pdf, '--pages', '1', '--out', layout)
            with open(planf, 'w') as f:
                json.dump(dict(PLAN, lists=[dict(PLAN['lists'][0], kind='ritual')]), f)
            r = run('convert_spells.py', layout, '--plan', planf, '--out', out)
            self.assertEqual(r.returncode, 1)
            with open(os.path.join(out, '_report.json')) as f:
                errors = json.dumps(json.load(f)['errors'])
            self.assertIn('learning_xp', errors)
            self.assertIn("'Range:'", errors)      # a label among its fields that a rite doesn't have


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class SameNameTest(ConvertSpellsTest):
    """A spell with the name of another source's spell is related to it by comparing their text."""
    def library(self, change=None):
        r, _ = self.convert()
        lib = os.path.join(self.d, 'library-data')
        os.makedirs(os.path.join(lib, 'spells'))
        glow = self.load('spells--glow.json')
        if change:
            glow['content'][-1]['text'] = change
        with open(os.path.join(lib, 'spells', 'glow.json'), 'w') as f:
            json.dump(dict(glow, source='OLD'), f)
        index = os.path.join(self.d, 'spells-index.json')
        with open(index, 'w') as f:
            json.dump([{'slug': 'glow', 'source': 'OLD'}], f)
        return lib, index

    def again(self, *args):
        r = run('convert_spells.py', self.layout, '--plan', os.path.join(self.d, 'plan.json'), '--out', self.out, *args)
        with open(os.path.join(self.out, '_report.json')) as f:
            return r, json.load(f)

    def test_the_same_words_are_a_reprint(self):
        lib, index = self.library()
        r, report = self.again('--taken', f'spells={index}', '--library-data', lib)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['same_name'], [{'category': 'spells', 'name': 'Glow', 'taken': 'glow',
                                                'relation': 'reprint-of'}])
        e = self.load('spells--glow-test.json')
        self.assertEqual(e['relations'], [{'role': 'reprint-of', 'to': 'spells/glow'}])
        rec = next(x for x in self.load('_records.json') if x['slug'] == 'glow-test')
        self.assertEqual(rec['relations'], e['relations'])
        self.assertEqual((rec['kind'], rec['cn']), ('petty', 0))

    def test_any_difference_is_a_replacement(self):
        lib, index = self.library(change='Your lamp glows without oil, for an hour.')
        r, report = self.again('--taken', index, '--library-data', lib)      # a bare path: the spells index
        self.assertEqual(report['same_name'][0]['relation'], 'replaces')
        self.assertEqual(self.load('spells--glow-test.json')['relations'], [{'role': 'replaces', 'to': 'spells/glow'}])

    def test_the_plans_relation_stands(self):
        lib, index = self.library()
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(dict(PLAN, relations={'spells/glow-test': [{'role': 'distinct-from', 'to': 'spells/glow'}]}), f)
        r, report = self.again('--taken', f'spells={index}', '--library-data', lib)
        self.assertEqual(report['same_name'][0]['relation'], 'from the plan')
        self.assertEqual(self.load('spells--glow-test.json')['relations'][0]['role'], 'distinct-from')

    def test_with_nothing_to_go_by_it_is_an_error(self):
        lib, index = self.library()
        r, report = self.again('--taken', f'spells={index}')
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any('spells/glow' in e['error'] and '--library-data' in e['error'] for e in report['errors']))


if __name__ == '__main__':
    unittest.main()
