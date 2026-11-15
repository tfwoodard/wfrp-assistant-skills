"""Tests for the plan options that read a letter-like entry (starts_at, subheadings, not_headings),
a backdrop read as text (a box marked "text"), flourishes (ornaments), drop capitals and styled runs
across line breaks, on an invented page the test draws itself: no book text.

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
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {
    'source': 'TEST', 'chapter': 'ch1',
    'entries': [
        {'name': 'Lantern Rules', 'page': 1, 'kind': 'procedure'},
        {'name': 'A Letter', 'page': 1, 'category': 'lore', 'kind': 'other', 'slug': 'a-letter',
         'starts_at': 'To the Keeper', 'subheadings': ['Oil']},
    ],
    'not_headings': [{'page': 1, 'text': 'Wen Tallow'}],
    'boxes': {'1.1': {'text': True}},
}


def draw(path):
    """One page: a chapter title; "Lantern Rules" with its last two lines over a tinted backdrop;
    then a letter: an address line, a larger line, a paragraph opening with a drop capital, a
    body-size bold section name, two lines of italics, a small flourish and a large signature."""
    img = os.path.join(os.path.dirname(path), 'tint.png')
    Image.new('RGB', (40, 40), (225, 215, 185)).save(img)
    c = canvas.Canvas(path, pagesize=A4)
    L = 60

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    text(L, 760, 'Lamplight', 'Helvetica-Bold', 30)
    text(L, 730, 'Lantern Rules', 'Helvetica-Bold', 18)
    text(L, 714, 'Every lantern is trimmed at dusk and filled at dawn.')
    text(L, 703, 'A keeper never leaves a lantern burning alone.')
    c.drawImage(img, L - 10, 676, 300, 24)
    text(L, 692, 'The tower lamp is the last to be put out.')
    text(L, 681, 'Its glass is cleaned once a week.')
    text(L, 645, 'To the Keeper of the North Tower,')
    text(L, 625, 'A note on lamps', 'Helvetica-Bold', 14)
    text(L + 30, 607, 'nce lit, a lamp is never left alone by its')
    text(L, 596, 'O', 'Helvetica-Bold', 30)
    text(L + 30, 596, 'keeper, whatever the hour or the weather.')
    text(L, 585, 'Every keeper knows it by heart.')
    text(L, 565, 'Oil', 'Helvetica-Bold')
    text(L, 554, 'Fill the lamp at dusk.')
    text(L, 543, 'Never let it run', 'Helvetica-Oblique')
    text(L, 532, 'dry before dawn.', 'Helvetica-Oblique')
    text(L + 100, 518, '~', size=7)
    text(L, 490, 'Wen Tallow', 'Helvetica', 26)
    for i in range(14):
        text(L, 460 - 11 * i, 'The keepers sign each letter with ink and tallow.')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class LetterEntriesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        pdf = os.path.join(d, 'page.pdf')
        draw(pdf)
        cls.layout = os.path.join(d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', cls.layout)
        assert r.returncode == 0, r.stderr
        cls.layout_stderr = r.stderr
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

    def test_converts_without_errors_and_accounts_for_every_word(self):
        self.assertEqual(self.result.returncode, 0, self.report['errors'])
        self.assertEqual(self.report['errors'], [])
        r = run('check_coverage.py', self.layout, self.out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_drop_capital_joins_its_paragraphs_first_line(self):
        with open(self.layout) as f:
            layout = json.load(f)
        self.assertEqual(len(layout['drop_capitals']), 1)
        self.assertIn('drop capital', self.layout_stderr)
        texts = [l['text'] for l in layout['lines']]
        self.assertIn('Once lit, a lamp is never left alone by its', texts)
        self.assertIn('keeper, whatever the hour or the weather.', texts)

    def test_a_box_marked_text_reads_in_place(self):
        content = self.load('lantern-rules.json')['content']
        self.assertEqual([b['type'] for b in content], ['paragraph'])
        self.assertTrue(content[0]['text'].endswith('cleaned once a week.'), content[0]['text'])

    def test_the_letter_starts_at_its_address_and_reads_its_headings(self):
        content = self.load('lore--a-letter.json')['content']
        self.assertTrue(content[0]['text'].startswith('To the Keeper'), content[0])
        heads = [(b['level'], b['text']) for b in content if b['type'] == 'heading']
        self.assertEqual(heads, [(2, 'A note on lamps'), (3, 'Oil')])

    def test_a_signature_named_in_not_headings_is_body_text(self):
        content = self.load('lore--a-letter.json')['content']
        self.assertTrue(any(b['type'] == 'paragraph' and b['text'].startswith('Wen Tallow') for b in content))

    def test_an_italic_run_over_a_line_break_is_marked_once(self):
        content = self.load('lore--a-letter.json')['content']
        para = next(b['text'] for b in content if b['type'] == 'paragraph' and b['text'].startswith('Fill'))
        self.assertEqual(para, 'Fill the lamp at dusk. *Never let it run dry before dawn*.')

    def test_flourishes_are_left_out_and_listed(self):
        self.assertEqual(self.report['ornaments'], [{'page': 1, 'text': '~'}])
        self.assertIn('~', self.report['left_out'])

    def test_a_missing_start_or_subheading_is_an_error(self):
        plan = dict(PLAN, entries=[PLAN['entries'][0],
                                   dict(PLAN['entries'][1], starts_at='Dear Nobody', subheadings=['Wax'])])
        p = os.path.join(self.tmp.name, 'bad-plan.json')
        with open(p, 'w') as f:
            json.dump(plan, f)
        out = os.path.join(self.tmp.name, 'bad')
        run('convert_rules.py', self.layout, '--plan', p, '--out', out)
        with open(os.path.join(out, '_report.json')) as f:
            errors = [e['error'] for e in json.load(f)['errors']]
        self.assertTrue(any("'Dear Nobody'" in e for e in errors), errors)
        self.assertTrue(any("'Wax'" in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
