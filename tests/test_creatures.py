"""Tests for creature profiles read from stat blocks (an entry's "stat_blocks"), trait entries
flagged from their names ("split_headings" with "name_flags"), and coverage counting a profile.
The page is invented and drawn by the test: no book text.

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

import creatures  # noqa: E402

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

HEADER = 'M WS BS S T I Ag Dex Int WP Fel W'
PLAN = {
    'source': 'TEST', 'chapter': 'ch12',
    'entries': [
        {'name': 'Wick Moths', 'page': 1, 'category': 'creatures', 'kind': 'creature', 'stat_blocks': True},
        {'name': 'Moth Traits', 'page': 1, 'kind': 'glossary',
         'split_headings': {'category': 'traits', 'name_flags': {'rated': 'Rating'}}},
    ],
}


def heading(text):
    return {'type': 'heading', 'level': 4, 'text': text}


def para(text):
    return {'type': 'paragraph', 'text': text}


def report():
    return {'errors': [], 'left_out': []}


class StatBlockTest(unittest.TestCase):
    def test_a_list_splits_at_commas_outside_brackets(self):
        self.assertEqual(creatures.split_list('Bite+4, Trained (Fetch, Guard), Size (Tiny).'),
                         ['Bite+4', 'Trained (Fetch, Guard)', 'Size (Tiny)'])

    def test_one_profile(self):
        rep = report()
        content, fields = creatures.stat_blocks(
            [para('Moths gather at lamps.'), heading(HEADER), para('6 25 - 5 10 40 50 - 5 10 - 3'),
             para('**Traits**: Flight 60, Size (Tiny) **Optional**: Swarm')], rep, 'Wick Moths')
        self.assertEqual(rep['errors'], [])
        self.assertEqual(content, [para('Moths gather at lamps.')])
        self.assertEqual(fields['characteristics']['WS'], 25)
        self.assertIsNone(fields['characteristics']['BS'])
        self.assertEqual((fields['traits'], fields['optional_traits']), (['Flight 60', 'Size (Tiny)'], ['Swarm']))
        self.assertIn(HEADER, rep['left_out'])

    def test_two_profiles_take_the_names_printed_above_them(self):
        rep = report()
        block = [heading(HEADER), para('4 30 30 30 30 30 30 30 30 30 30 12'), para('**Traits**: Weapon+7')]
        content, fields = creatures.stat_blocks(
            [para('Two old keepers haunt the tower.'), para('Grizzle Wick – Elder Keeper'), *block,
             para('Ash Tallow – Young Keeper'), *block], rep, 'Keepers')
        self.assertEqual(rep['errors'], [])
        self.assertEqual([p['name'] for p in fields['profiles']], ['Grizzle Wick – Elder Keeper', 'Ash Tallow – Young Keeper'])
        self.assertEqual(content, [para('Two old keepers haunt the tower.')])

    def test_a_short_values_row_or_an_unnamed_profile_is_an_error(self):
        rep = report()
        creatures.stat_blocks([heading(HEADER), para('4 30 30')], rep, 'here')
        self.assertEqual(len(rep['errors']), 2)                 # the short row, and so no profile
        rep = report()
        block = [heading(HEADER), para('4 30 30 30 30 30 30 30 30 30 30 12')]
        creatures.stat_blocks([*block, *block], rep, 'here')
        self.assertTrue(any('no name line' in e['error'] for e in rep['errors']), rep['errors'])


def draw(path):
    """A creature with its stat block, and a list of traits headed at 12pt."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    def text(y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(60, y, s)

    text(h - 90, 'Lamplight Beasts', 'Helvetica-Bold', 30)
    y = h - 130
    text(y, 'Wick Moths', 'Helvetica-Bold', 18); y -= 16
    for s in ('Wick moths gather at every lamp on the towpath and', 'eat the wicks when the keepers are not looking.'):
        text(y, s); y -= 11
    y -= 4
    text(y, HEADER, 'Helvetica-Bold', 11); y -= 13
    text(y, '6 25 - 5 10 40 50 - 5 10 - 3', size=10); y -= 13
    c.setFont('Helvetica-Bold', 9); c.drawString(60, y, 'Traits:')
    c.setFont('Helvetica', 9); c.drawString(95, y, 'Flight 60, Size (Tiny), Weapon+2'); y -= 11
    c.setFont('Helvetica-Bold', 9); c.drawString(60, y, 'Optional:')
    c.setFont('Helvetica', 9); c.drawString(105, y, 'Swarm, Trained (Fetch, Guard)'); y -= 26
    text(y, 'Moth Traits', 'Helvetica-Bold', 18); y -= 16
    text(y, 'These traits suit any small flying pest.'); y -= 16
    for head, body in (('Flight (Rating)', 'The creature flies Rating yards a turn.'),
                       ('Swarm', 'The creature attacks as a cloud of many.')):
        text(y, head, 'Helvetica-Bold', 12); y -= 13
        text(y, body); y -= 16
    for i in range(16):
        text(y - 11 * i, ('The keepers trap the moths in jars of', 'oil and sell them to the guild store',
                          'for a penny a dozen in the spring.')[i % 3])
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab is needed to draw the fixture PDF')
class CreaturePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        pdf = os.path.join(d, 'page.pdf')
        draw(pdf)
        cls.layout = os.path.join(d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--out', cls.layout)
        assert r.returncode == 0, r.stderr
        plan = os.path.join(d, 'plan.json')
        with open(plan, 'w') as f:
            json.dump(PLAN, f)
        cls.out = os.path.join(d, 'out')
        cls.result = run('convert_rules.py', cls.layout, '--plan', plan, '--out', cls.out)
        with open(os.path.join(cls.out, '_report.json')) as f:
            cls.report = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, name):
        with open(os.path.join(self.out, name)) as f:
            return json.load(f)

    def test_converts_without_errors_and_accounts_for_every_word(self):
        self.assertEqual(self.report['errors'], [], self.result.stdout)
        r = run('check_coverage.py', self.layout, self.out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_creature_carries_its_profile(self):
        moth = self.load('creatures--wick-moths.json')
        self.assertEqual(moth['fields']['characteristics']['Ag'], 50)
        self.assertEqual(moth['fields']['optional_traits'], ['Swarm', 'Trained (Fetch, Guard)'])
        self.assertEqual([b['type'] for b in moth['content']], ['paragraph'])

    def test_traits_are_flagged_rated_from_their_names(self):
        self.assertTrue(self.load('traits--flight-rating.json')['fields']['rated'])
        self.assertFalse(self.load('traits--swarm.json')['fields']['rated'])


if __name__ == '__main__':
    unittest.main()
