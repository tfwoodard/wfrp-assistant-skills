"""Tests for price tables read as trappings (a table plan's "items"), descriptions moved to their
items ("describes_items"), headings split into entries ("split_headings" with "dividers"), a cell
holding two columns ("split_column"), and coverage counting a trapping's printed values. The page
is invented and drawn by the test: no book text.

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

import items  # noqa: E402

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

ROWS = [('', '', 'BRASS*', ''), ('(2H) Great Lantern', '3GC', '2', 'Rare'), ('Wick Spool', '4/–', '0', 'Common'),
        ('', '', 'TIN', ''), ('Wick Spool', '2/–', '0', 'Common'), ('Snuffer', '1/–**', '0', 'Scarce'),
        ('Fish Hooks (12)', '1/–', '0', 'Common')]
PLAN = {
    'source': 'TEST', 'chapter': 'ch11',
    'entries': [
        {'name': 'Lamp Gear', 'page': 1, 'kind': 'other', 'describes_items': True},
        {'name': 'Lamp Qualities', 'page': 1, 'kind': 'other',
         'split_headings': {'category': 'qualities', 'kind': 'lamp-quality',
                            'dividers': {'Lamp Flaws': 'lamp-flaw'}}},
    ],
    'tables': {'1.1': {'items': {'kind': 'lamp', 'fields': {'Price': 'price', 'Enc': 'enc',
                                                            'Availability': 'availability'}}}},
    'rename': {'1.1/Tin/Wick Spool': 'Wick Spool (Tin)'},
}


def draw(path):
    """Left column: "Lamp Gear" with an intro and three bold-labelled descriptions, then "Lamp
    Qualities" with headings Bright, Smoky, the divider Lamp Flaws, and Dim. Right column: a
    boxed, ruled price table titled LAMP GEAR, with group rows and two footnotes under it."""
    img = os.path.join(os.path.dirname(path), 'tint.png')
    Image.new('RGB', (40, 40), (225, 215, 185)).save(img)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    L, R = 50, w / 2 + 6

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    def labelled(y, lab, rest):
        text(L, y, lab, 'Helvetica-Bold')
        text(L + c.stringWidth(lab, 'Helvetica-Bold', 9) + 3, y, rest)

    text(w / 2 - 50, h - 85, 'Lamplight', 'Helvetica-Bold', 30)
    y = h - 115
    text(L, y, 'Lamp Gear', 'Helvetica-Bold', 18); y -= 16
    for s in ('Keepers buy their gear from the guild', 'store at the foot of the old tower.'):
        text(L, y, s); y -= 11
    y -= 4
    labelled(y, 'Snuffer:', 'Puts a flame out without smoke.'); y -= 15
    labelled(y, 'Fish Hooks:', 'Bent wire for the moat.'); y -= 15
    labelled(y, 'Lamp Oil:', 'Sold by the jug at the store.'); y -= 24
    text(L, y, 'Lamp Qualities', 'Helvetica-Bold', 18); y -= 16
    for s in ('Some lamps are better than others.', 'Each quality is named on its label.'):
        text(L, y, s); y -= 11
    for head, body in (('Bright', 'Lights a whole room.'), ('Smoky', 'Fills the room with soot.'),
                       ('Lamp Flaws', 'Flaws are marked in red.'), ('Dim', 'Lights only the table.')):
        y -= 6
        text(L, y, head, 'Helvetica-Bold', 12); y -= 14
        text(L, y, body); y -= 11

    x0, x1, top = R, R + 250, h - 115
    xs = (x0 + 10, x0 + 105, x0 + 150, x0 + 180)
    height = 30 + 14 * (len(ROWS) + 1) + 30
    c.drawImage(img, x0, top - height, x1 - x0, height)
    y = top - 16
    text(x0 + 10, y, 'LAMP GEAR', 'Helvetica-Bold', 12)
    y -= 18
    for x, s in zip(xs, ('Item', 'Price', 'Enc', 'Availability')):
        text(x + 2, y, s, 'Helvetica-Bold')
    y -= 4
    rows_top = y
    c.setLineWidth(0.5)
    for row in ROWS:
        c.line(x0 + 10, y, x1 - 10, y)
        y -= 10
        for x, s in zip(xs, row):
            text(x + 2, y, s)
        y -= 4
    c.line(x0 + 10, y, x1 - 10, y)
    for x in xs[1:]:
        c.line(x - 1, rows_top + 14, x - 1, y)
    y -= 16                                   # footnotes start left of the rules: not a row
    text(x0 + 4, y, '* Brass lamps tarnish in the sea air, so keepers polish them weekly.', size=8); y -= 10
    text(x0 + 4, y, '** Keep it dry.', size=8)
    filler = ('The guild store opens at dusk and closes', 'at dawn, and the keepers queue', 'outside its door with their',
              'empty jugs and spent wicks, talking', 'of storms and ships and the', 'price of oil this season.')
    for i in range(18):
        text(R, top - height - 24 - 11 * i, filler[i % len(filler)])
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


class ItemRowsTest(unittest.TestCase):
    def report(self):
        return {'errors': [], 'left_out': []}

    def test_groups_two_handed_and_marks(self):
        cols = ['Item', 'Price', 'Enc', 'Availability']
        rep = self.report()
        got = items.item_rows(cols, [list(r) for r in ROWS], PLAN['tables']['1.1']['items'],
                              {'*': 'Tarnishes.', '**': 'Keep dry.'}, rep, 'here')
        self.assertEqual(rep['errors'], [])
        lantern = got[0]
        self.assertEqual(lantern['name'], 'Great Lantern')
        self.assertEqual(lantern['fields'], {'kind': 'lamp', 'group': 'Brass', 'two_handed': True, 'price': '3GC',
                                             'enc': '2', 'availability': 'Rare', 'notes': ['Tarnishes.']})
        snuffer = got[3]
        self.assertEqual((snuffer['fields']['price'], snuffer['fields']['notes'], snuffer['fields']['group']),
                         ('1/–', ['Keep dry.'], 'Tin'))

    def test_a_mark_without_a_footnote_and_a_footnote_without_a_mark_are_errors(self):
        rep = self.report()
        items.item_rows(['Item', 'Price', 'Enc', 'Availability'], [list(r) for r in ROWS],
                        PLAN['tables']['1.1']['items'], {'*': 'Tarnishes.', '***': 'Unused.'}, rep, 'here')
        self.assertEqual(len(rep['errors']), 2, rep['errors'])

    def test_a_cell_holding_two_columns_is_split(self):
        rep = self.report()
        cols, rows = items.split_column(['Item', 'Cost', 'Avail Item', 'Cost'], [['Hook', '1d', 'Common Rope', '2d']],
                                        2, 1, rep, 'here')
        self.assertEqual((cols, rows), (['Item', 'Cost', 'Avail', 'Item', 'Cost'],
                                        [['Hook', '1d', 'Common', 'Rope', '2d']]))
        items.split_column(cols, [['Hook', '1d', 'Common', 'x', 'y']], 2, 1, rep, 'here')
        self.assertEqual(len(rep['errors']), 2)       # the header's cell and the row's: nothing to split

    def test_a_label_names_an_item_allowing_for_quantity_and_unit(self):
        self.assertTrue(items.same_item('Fish Hooks (12)', 'Fish Hook'))
        self.assertTrue(items.same_item('Ale, pint', 'Ale'))
        self.assertTrue(items.same_item('Room, common/night', 'Room, Common'))
        self.assertFalse(items.same_item('Ale, pint', 'Ale, keg'))


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class PriceTablePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        pdf = os.path.join(d, 'page.pdf')
        draw(pdf)
        cls.layout = os.path.join(d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', cls.layout)
        assert r.returncode == 0, r.stderr
        cls.plan = os.path.join(d, 'plan.json')
        with open(cls.plan, 'w') as f:
            json.dump(PLAN, f)
        cls.out = os.path.join(d, 'out')
        cls.result = run('convert_rules.py', cls.layout, '--plan', cls.plan, '--out', cls.out)
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

    def test_each_row_is_a_trapping(self):
        names = sorted(f for f in os.listdir(self.out) if f.startswith('trappings--') and f.endswith('.json'))
        self.assertEqual(names, ['trappings--fish-hooks-12.json', 'trappings--great-lantern.json',
                                 'trappings--snuffer.json', 'trappings--wick-spool-tin.json',
                                 'trappings--wick-spool.json'])
        lantern = self.load('trappings--great-lantern.json')
        self.assertEqual(lantern['fields']['notes'], ['Brass lamps tarnish in the sea air, so keepers polish them weekly.'])
        self.assertEqual(lantern['section'], 'Lamp Qualities')     # the entry the table falls in
        with open(os.path.join(self.out, '_records.json')) as f:
            rec = next(r for r in json.load(f) if r['slug'] == 'great-lantern')
        self.assertEqual((rec['_category'], rec['price'], rec['two_handed']), ('trappings', '3GC', True))

    def test_a_renamed_item_and_its_group(self):
        spool = self.load('trappings--wick-spool-tin.json')
        self.assertEqual((spool['name'], spool['fields']['group']), ('Wick Spool (Tin)', 'Tin'))

    def test_descriptions_move_to_their_items(self):
        self.assertEqual(self.load('trappings--snuffer.json')['content'],
                         [{'type': 'paragraph', 'text': 'Puts a flame out without smoke.'}])
        self.assertEqual(self.load('trappings--fish-hooks-12.json')['content'][0]['text'], 'Bent wire for the moat.')
        gear = self.load('lamp-gear.json')['content']
        self.assertEqual([b['text'][:9] for b in gear], ['Keepers b', '**Lamp Oi'])
        self.assertEqual([k['label'] for k in self.report['labels_kept']], ['Lamp Oil'])

    def test_headings_split_into_qualities_with_a_divider(self):
        bright = self.load('qualities--bright.json')
        self.assertEqual((bright['fields']['kind'], bright['content'][0]['text']), ('lamp-quality', 'Lights a whole room.'))
        self.assertEqual(self.load('qualities--dim.json')['fields']['kind'], 'lamp-flaw')
        self.assertFalse(os.path.exists(os.path.join(self.out, 'qualities--lamp-flaws.json')))
        parent = [b['text'] for b in self.load('lamp-qualities.json')['content']]
        self.assertEqual(parent[-2:], ['Lamp Flaws', 'Flaws are marked in red.'])

    def test_two_items_of_one_name_are_an_error(self):
        plan = dict(PLAN, rename={})
        p = os.path.join(self.tmp.name, 'plan2.json')
        with open(p, 'w') as f:
            json.dump(plan, f)
        out = os.path.join(self.tmp.name, 'out2')
        run('convert_rules.py', self.layout, '--plan', p, '--out', out)
        with open(os.path.join(out, '_report.json')) as f:
            errors = [e['error'] for e in json.load(f)['errors']]
        self.assertTrue(any("2 items named 'Wick Spool'" in e for e in errors), errors)

    def again(self, tag, plan=PLAN, other=None):
        """Convert once more: with `other`, another source's library holds that Snuffer."""
        d = os.path.join(self.tmp.name, tag)
        os.makedirs(os.path.join(d, 'lib', 'trappings'))
        with open(os.path.join(d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        args = []
        if other:
            with open(os.path.join(d, 'lib', 'trappings', 'snuffer.json'), 'w') as f:
                json.dump(other, f)
            with open(os.path.join(d, 'index.json'), 'w') as f:
                json.dump([{'slug': 'snuffer', 'source': 'OLD'}], f)
            args = ['--taken', 'trappings=' + os.path.join(d, 'index.json'), '--library-data', os.path.join(d, 'lib')]
        run('convert_rules.py', self.layout, '--plan', os.path.join(d, 'plan.json'), '--out', os.path.join(d, 'out'), *args)
        with open(os.path.join(d, 'out', '_report.json')) as f:
            report = json.load(f)
        return os.path.join(d, 'out'), report

    def test_an_item_the_same_throughout_is_a_reprint(self):
        other = dict(self.load('trappings--snuffer.json'), source='OLD')
        out, report = self.again('same', other=other)
        self.assertEqual(report['errors'], [])
        with open(os.path.join(out, 'trappings--snuffer-test.json')) as f:
            self.assertEqual(json.load(f)['relations'], [{'role': 'reprint-of', 'to': 'trappings/snuffer'}])

    def test_an_item_with_another_price_is_not_a_reprint(self):
        other = dict(self.load('trappings--snuffer.json'), source='OLD')
        other['fields'] = dict(other['fields'], price='9/–')         # the words about it are the same
        out, report = self.again('dearer', other=other)
        with open(os.path.join(out, 'trappings--snuffer-test.json')) as f:
            self.assertEqual(json.load(f)['relations'], [{'role': 'version-of', 'to': 'trappings/snuffer'}])
        self.assertEqual([s['relation'] for s in report['same_name']], ['version-of'])

    def test_the_plan_can_give_an_item_its_slug(self):
        out, report = self.again('slug', plan=dict(PLAN, item_slugs={'1.1/Snuffer': 'snuffer-keepers'}))
        self.assertEqual(report['errors'], [])
        self.assertTrue(os.path.exists(os.path.join(out, 'trappings--snuffer-keepers.json')))
        self.assertFalse(os.path.exists(os.path.join(out, 'trappings--snuffer.json')))


if __name__ == '__main__':
    unittest.main()
