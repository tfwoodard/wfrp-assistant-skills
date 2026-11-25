"""plan_pack.py: a plan with no book text in it, rebuilt from the installer's own copy.

Uses the invented "Lamplight" chapter the converter tests draw."""
import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_convert_rules import HAVE_LIBS, PLAN, SCRIPTS, draw_chapter, run  # noqa: E402

sys.path.insert(0, SCRIPTS)
import plan_pack  # noqa: E402

PRINTED = ['Trimming Wicks', 'Smoked', 'Dread (Rating)', 'Wick Rot', 'Wick Lengths', 'Lamplight', 'Contraction']


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class PlanPackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.pdf = os.path.join(self.d, 'chapter.pdf')
        draw_chapter(self.pdf)
        self.layout_path = os.path.join(self.d, 'layout.json')
        r = run('pdf_layout.py', self.pdf, '--pages', '1-2', '--boxes', '--out', self.layout_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.layout_path) as f:
            self.layout = json.load(f)
        self.lib = os.path.join(self.d, 'library-data')
        os.makedirs(os.path.join(self.lib, 'rules'))
        with open(os.path.join(self.lib, 'rules', '_index.json'), 'w') as f:
            json.dump([{'slug': 'oil-lore', 'name': 'Oil Lore'}], f)
        self.plan = copy.deepcopy(PLAN)
        self.plan['entries'][0]['name'] = 'Lamplight: Trimming Wicks'        # the Librarian's own wording
        self.plan['entries'][0]['heading'] = 'Trimming Wicks'
        self.plan['relations'] = {'rules/smoked': [{'to': 'rules/oil-lore', 'role': 'adds-to'}]}
        self.plan['entries'].append({'name': 'Snuffing Spoon', 'page': 2})    # typed by hand: not printed

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_pack_holds_no_book_words_and_rebuilds_the_plan(self):
        pack, kept = plan_pack.export(self.plan, self.layout, self.lib)
        said = json.dumps(pack, ensure_ascii=False)
        for words in PRINTED + ['Snuffing', 'oil-lore', 'smoked', 'How long a wick burns']:
            self.assertNotIn(words, said)
        self.assertEqual((pack['source'], pack['chapter']), ('TEST', 'ch5'))  # which book: said plainly
        self.assertIn('kind', said)                                          # the tool's own words stay
        rebuilt, left = plan_pack.install(pack, self.layout, self.lib)
        self.assertEqual(left, [])
        self.assertEqual(rebuilt, kept)
        names = [e['name'] for e in rebuilt['entries']]
        self.assertIn('Lamplight: Trimming Wicks', names)                    # rebuilt word by word
        self.assertNotIn('Snuffing Spoon', names)                            # not printed: left out whole
        self.assertIn('entries/4/whole', pack['left_out'])
        self.assertEqual(sorted(x for x in pack['left_out'] if not x.startswith('entries/4')),
                         ['entries/1/aliases/0', 'intro/slug', 'tables/1.1/about'])  # the Librarian's own words
        self.assertEqual(rebuilt['relations'], self.plan['relations'])       # slugs from the library
        self.assertEqual(rebuilt['tables']['1.1']['title'], 'Wick Lengths')
        self.assertFalse(any('Snuffing' in p for p in pack['left_out']))     # positions only

    def test_another_printing_rebuilds_what_it_has_and_says_what_it_lacks(self):
        pack, kept = plan_pack.export(self.plan, self.layout, self.lib)
        other = copy.deepcopy(self.layout)
        for l in other['lines']:
            l['text'] = l['text'].replace('Dread', 'Fright')
        rebuilt, left = plan_pack.install(pack, other, self.lib)
        self.assertNotIn('Dread', [e['name'] for e in rebuilt['entries']])
        self.assertIn(['entries', 2, 'whole'], left)                          # its name is gone: so is it

    def test_the_command_line_round_trip(self):
        plan = os.path.join(self.d, 'plan.json')
        with open(plan, 'w') as f:
            json.dump(self.plan, f)
        pack, back = os.path.join(self.d, 'pack.json'), os.path.join(self.d, 'back.json')
        r = run('plan_pack.py', 'export', plan, self.layout_path, '--out', pack, '--library-data', self.lib, '--pdf', self.pdf)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stderr, r'\d+ values left out, the rest rebuilds from the book')
        r = run('plan_pack.py', 'install', pack, self.layout_path, '--out', back, '--library-data', self.lib, '--pdf', self.pdf)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(back) as f:
            got = json.load(f)
        self.assertEqual(len(got['entries']), 4)
        r = run('convert_rules.py', self.layout_path, '--plan', back, '--out', os.path.join(self.d, 'out'))
        self.assertEqual(r.returncode, 0, r.stderr)                          # the rebuilt plan converts


if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class PacksFolderTest(PlanPackTest):
    """Packs are filed by the PDF they were made from; a new PDF of a source gets its own folder."""
    test_a_pack_holds_no_book_words_and_rebuilds_the_plan = None
    test_another_printing_rebuilds_what_it_has_and_says_what_it_lacks = None
    test_the_command_line_round_trip = None

    def test_packs_are_kept_by_pdf(self):
        packs = os.path.join(self.d, 'packs')
        pack, kept = plan_pack.export(self.plan, self.layout, self.lib, self.pdf)
        path = plan_pack.into(pack, packs, 'Lamplight Almanac')
        sha = plan_pack.pdf_sha256(self.pdf)
        self.assertEqual(path, os.path.join(packs, 'TEST', sha[:12], 'ch5.json'))
        with open(os.path.join(packs, 'TEST', sha[:12], 'edition.json')) as f:
            ed = json.load(f)
        self.assertEqual((ed['pdf_sha256'], ed['pdf_bytes'], ed['title']), (sha, os.path.getsize(self.pdf), 'Lamplight Almanac'))
        self.assertEqual(ed['chapters']['ch5'], {'chapter': 'ch5', 'pages': '1-2', 'left_out': len(pack['left_out'])})
        self.assertEqual(pack['layout']['pages'], '1-2')
        self.assertIn('--boxes', plan_pack.layout_command(pack))
        # a corrected PDF of the same book: a folder of its own, beside the first
        fixed = os.path.join(self.d, 'fixed.pdf')
        with open(self.pdf, 'rb') as f, open(fixed, 'wb') as g:
            g.write(f.read() + b'\n%corrected\n')
        exact, others = plan_pack.find(fixed, packs)
        self.assertIsNone(exact)
        self.assertEqual([o[1] for o in others], [os.path.join(packs, 'TEST', sha[:12])])
        pack2, _ = plan_pack.export(self.plan, self.layout, self.lib, fixed)
        plan_pack.into(pack2, packs)
        self.assertEqual(len(os.listdir(os.path.join(packs, 'TEST'))), 2)
        exact, others = plan_pack.find(self.pdf, packs, 'TEST')
        self.assertEqual(exact, os.path.join(packs, 'TEST', sha[:12]))
        r = run('plan_pack.py', 'find', self.pdf, '--packs', packs)
        self.assertIn('packs made from this PDF', r.stdout)
