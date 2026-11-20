"""Tests for stat blocks printed in a box of their own, on invented lines and an invented page.

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
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

HEAD = 'M WS BS S T I Ag Dex Int WP Fel W'
VALS = '4 30 – 35 40 25 30 20 45 50 15 12'


def line(*spans, bold=None):
    """A line of (text, bold) spans; a bare string is one span, not bold."""
    spans = [{'text': t, 'bold': b, 'italic': False, 'size': 9.0} for t, b in
             [(s, False) if isinstance(s, str) else s for s in spans]]
    return {'text': ' '.join(s['text'] for s in spans), 'spans': spans, 'size': 9.0,
            'bold': all(s['bold'] for s in spans) if bold is None else bold}


def keeper():
    return [line(('OLD HANNE', True)), line(('KEEPER OF FLAMES (SILVER 3)', True)), line((HEAD, True)), line(VALS),
            line(('Traits:', True), 'Night Vision, Weapon (Boat Hook) +6'),
            line(('Skills:', True), 'Climb 45, Lore (Wicks 60,'), line('Tides 55), Perception 50'),
            line(('Spells: Petty:', True), 'Glow, Far Beam'), line(('Lore of Lamps:', True), 'Kindle the Great Lamp,'),
            line('Call the Fog'),
            line(('Note:', True), 'Hanne keeps her rites in a', ('Sealed', True), 'ledger.'),
            line(('Trappings:', True), 'Brass Lantern, Keys'),
            line(('The Brass Lantern', True)), line('It has never gone out.')]


class BoxProfileTest(unittest.TestCase):
    def setUp(self):
        self.report = {'errors': [], 'questions': [], 'left_out': []}

    def test_name_title_values_lists_spells_and_notes(self):
        p, after = creatures.box_profile(keeper(), self.report, 'Old Hanne')
        self.assertEqual(self.report['errors'], [])
        self.assertEqual((p['name'], p['title']), ('Old Hanne', 'Keeper of Flames (Silver 3)'))
        self.assertEqual(p['characteristics']['WS'], 30)
        self.assertIsNone(p['characteristics']['BS'])
        self.assertEqual(list(p['characteristics']), HEAD.split())
        self.assertEqual(p['traits'], ['Night Vision', 'Weapon (Boat Hook) +6'])
        self.assertEqual(p['skills'], ['Climb 45', 'Lore (Wicks 60, Tides 55)', 'Perception 50'])
        self.assertEqual(p['spells'], {'Petty': ['Glow', 'Far Beam'],
                                       'Lore of Lamps': ['Kindle the Great Lamp', 'Call the Fog']})
        self.assertEqual(p['special'], [{'label': 'Note', 'text': 'Hanne keeps her rites in a Sealed ledger.'}])
        self.assertEqual(p['trappings'], ['Brass Lantern', 'Keys'])          # read on after the note
        self.assertEqual([l['label'] for l in p['lines']],
                         ['Traits', 'Skills', 'Spells: Petty', 'Lore of Lamps', 'Note', 'Trappings'])
        # A line all in bold with no colon heads what follows the profile.
        self.assertEqual([l['text'] for l in after], ['The Brass Lantern', 'It has never gone out.'])

    def test_spells_without_groups_are_a_list_and_groups_can_follow_a_bare_label(self):
        lines = [line(('FOG WISP', True)), line((HEAD, True)), line(VALS), line(('Spells:', True), 'Glow, Gust')]
        p, _ = creatures.box_profile(lines, self.report, 'Fog Wisp')
        self.assertEqual(p['spells'], ['Glow', 'Gust'])
        lines = lines[:3] + [line(('Spells:', True)), line(('Petty Magic Spells:', True), 'Glow'),
                             line(('Hanne’s Lamp Magic:', True), 'Far Beam')]
        p, _ = creatures.box_profile(lines, self.report, 'Fog Wisp')
        self.assertEqual(p['spells'], {'Petty Magic Spells': ['Glow'], 'Hanne’s Lamp Magic': ['Far Beam']})

    def test_a_labelled_paragraph_that_only_looks_like_a_spell_group_is_special(self):
        lines = [line(('FOG WISP', True)), line((HEAD, True)), line(VALS), line(('Traits:', True), 'Flight 40'),
                 line(('Cold Magic:', True), 'The wisp chills all within reach.')]
        p, _ = creatures.box_profile(lines, self.report, 'Fog Wisp')
        self.assertNotIn('spells', p)
        self.assertEqual(p['special'][0]['label'], 'Cold Magic')

    def test_a_profile_wrapped_in_a_narrow_box(self):
        lines = [line(('PIER MULE', True)), line(('M WS BS S T I', True)), line('6 20 – 35 40 15'),
                 line(('Ag Dex Int WP Fel W', True)), line('25 – 10 15 20 18'),
                 line(('Traits:', True), 'Stride, Weapon +5'), line(('The Casks', True)),
                 line('It carries the oil casks.')]
        p, after = creatures.box_profile(lines, self.report, 'Pier Mule')
        self.assertEqual(self.report['errors'], [])
        self.assertEqual(p['name'], 'Pier Mule')
        self.assertNotIn('title', p)                         # the first header is not a title line
        self.assertEqual(p['characteristics'], {'M': 6, 'WS': 20, 'BS': None, 'S': 35, 'T': 40, 'I': 15, 'Ag': 25,
                                                'Dex': None, 'Int': 10, 'WP': 15, 'Fel': 20, 'W': 18})
        self.assertEqual(p['Traits'] if 'Traits' in p else p['traits'], ['Stride', 'Weapon +5'])
        self.assertEqual(self.report['left_out'], ['M WS BS S T I', 'Ag Dex Int WP Fel W'])
        self.assertEqual([l['text'] for l in after], ['The Casks', 'It carries the oil casks.'])

    def test_a_wrapped_profile_whose_second_row_falls_short_is_an_error(self):
        lines = [line(('PIER MULE', True)), line(('M WS BS S T I', True)), line('6 20 – 35 40 15'),
                 line(('Ag Dex Int WP Fel W', True)), line('25 – 10'), line(('Traits:', True), 'Stride')]
        p, _ = creatures.box_profile(lines, self.report, 'Pier Mule')
        self.assertIsNone(p)
        self.assertIn('6 characteristics', self.report['errors'][0]['error'])

    def test_values_that_do_not_match_the_header_are_an_error(self):
        p, after = creatures.box_profile([line(('FOG WISP', True)), line((HEAD, True)), line('4 30 35')],
                                         self.report, 'Fog Wisp')
        self.assertIsNone(p)
        self.assertIn('12 characteristics', self.report['errors'][0]['error'])

    def test_fields_for_one_profile_and_for_several(self):
        p, _ = creatures.box_profile(keeper(), self.report, 'Old Hanne')
        f = creatures.profile_fields([p], 'Old Hanne', self.report)
        self.assertNotIn('profile_name', f)                 # the entry's own name, printed again
        self.assertNotIn('lines', f)
        self.assertEqual(f['title'], 'Keeper of Flames (Silver 3)')
        for word in ('Old Hanne', 'Traits', 'Skills', 'Spells', 'Petty', 'Lore of Lamps', 'Trappings', HEAD):
            self.assertIn(word, self.report['left_out'])    # printed words the fields hold as keys
        self.assertNotIn('Note', self.report['left_out'])   # ...but a note's label is kept beside its text
        f = creatures.profile_fields([p], 'Hanne', self.report)
        self.assertEqual(f['profile_name'], 'Old Hanne')
        q, _ = creatures.box_profile(keeper(), self.report, 'x')
        f = creatures.profile_fields([p, q], 'The Keepers', self.report)
        self.assertEqual([x['name'] for x in f['profiles']], ['Old Hanne', 'Old Hanne'])
        self.assertEqual(f['profiles'][0]['traits'], ['Night Vision', 'Weapon (Boat Hook) +6'])

    def test_a_profile_as_a_block_keeps_its_lines_as_printed(self):
        p, _ = creatures.box_profile(keeper(), self.report, 'Old Hanne')
        b = creatures.profile_block(p)
        self.assertEqual((b['type'], b['name'], b['meta']), ('profile', 'Old Hanne', 'Keeper of Flames (Silver 3)'))
        self.assertEqual(b['lines'][0], {'label': 'Traits', 'text': 'Night Vision, Weapon (Boat Hook) +6'})


def draw_page(path):
    """A creature's entry with its stat block in a panel, and a rite whose servant's profile sits
    in a panel inside the rite."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    panel = ImageReader(Image.new('RGB', (40, 40), (230, 220, 190)))

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)
        return x + c.stringWidth(s, font, size)

    def block(x, y, name, rows):
        text(x, y, name, 'Helvetica-Bold', 10); y -= 12
        text(x, y, HEAD, 'Helvetica-Bold', 10); y -= 12
        text(x, y, VALS); y -= 11
        for lab, rest in rows:
            xx = text(x, y, lab, 'Helvetica-Bold') + 3 if lab else x
            text(xx, y, rest); y -= 11

    text(150, h - 70, 'THE LANTERN TRADES', 'Helvetica-Bold', 30)
    text(50, h - 110, 'Fog Wisp', 'Helvetica-Bold', 19)
    text(50, h - 126, 'Wisps gather where a lamp has failed.')
    c.drawImage(panel, 44, h - 230, 250, 90)
    block(52, h - 152, 'FOG WISP', [('Traits:', 'Flight 40, Ethereal'), ('Chill:', 'Those it touches shiver for'),
                                    ('', 'a night.')])
    text(50, h - 270, 'Raising a Lamp Servant', 'Helvetica-Bold', 19)
    text(50, h - 286, 'The keeper binds a servant of brass.')
    c.drawImage(panel, 44, h - 370, 250, 70)
    block(52, h - 312, 'LAMP SERVANT', [('Traits:', 'Construct, Stupid')])
    for k in range(4):
        text(320, h - 126 - 11 * k, 'Gulls circle the tower all day.')
    c.setFont('Helvetica', 9)
    c.drawString(w / 2, 20, '1')
    c.showPage()
    c.save()


PLAN = {'source': 'TEST', 'chapter': 'ch9',
        'entries': [{'name': 'Fog Wisp', 'page': 1, 'category': 'creatures', 'kind': 'creature', 'stat_blocks': True},
                    {'name': 'Raising a Lamp Servant', 'page': 1, 'kind': 'procedure'}],
        'boxes': {'1.1': {'profile': True}, '1.2': {'profile': True}}}


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class ProfileBoxesInAChapterTest(unittest.TestCase):
    def test_a_creatures_box_gives_its_fields_and_anothers_a_profile_block(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, layout, planf, out = (os.path.join(d, n) for n in ('p.pdf', 'layout.json', 'plan.json', 'out'))
            draw_page(pdf)
            run = lambda s, *a: subprocess.run([sys.executable, os.path.join(SCRIPTS, s), *a],  # noqa: E731
                                               capture_output=True, text=True)
            self.assertEqual(run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', layout).returncode, 0)
            with open(planf, 'w') as f:
                json.dump(PLAN, f)
            r = run('convert_rules.py', layout, '--plan', planf, '--out', out)
            with open(os.path.join(out, '_report.json')) as f:
                self.assertEqual(json.load(f)['errors'], [], r.stdout)
            with open(os.path.join(out, 'creatures--fog-wisp.json')) as f:
                wisp = json.load(f)
            self.assertEqual(wisp['fields']['traits'], ['Flight 40', 'Ethereal'])
            self.assertEqual(wisp['fields']['characteristics']['W'], 12)
            self.assertEqual(wisp['fields']['special'], [{'label': 'Chill', 'text': 'Those it touches shiver for a night.'}])
            self.assertEqual([b['type'] for b in wisp['content']], ['paragraph'])     # the box left its text
            with open(os.path.join(out, 'raising-a-lamp-servant.json')) as f:
                rite = json.load(f)
            profile = next(b for b in rite['content'] if b['type'] == 'profile')
            self.assertEqual(rite['content'][0]['text'], 'The keeper binds a servant of brass.')
            self.assertEqual(profile['name'], 'Lamp Servant')
            self.assertEqual(profile['lines'], [{'label': 'Traits', 'text': 'Construct, Stupid'}])
            self.assertNotIn('characteristics', rite['fields'])
            with open(os.path.join(out, '_records.json')) as f:
                rec = next(x for x in json.load(f) if x['slug'] == 'fog-wisp')
            self.assertEqual(rec['traits'], ['Flight 40', 'Ethereal'])
            self.assertNotIn('special', rec)
            cov = run('check_coverage.py', layout, out)
            self.assertIn('every word', cov.stdout, cov.stdout)


if __name__ == '__main__':
    unittest.main()
