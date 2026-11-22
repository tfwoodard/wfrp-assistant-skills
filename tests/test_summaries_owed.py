"""summaries_owed.py and the one-step sheet: what a sheet still lacks, from an invented library."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_character import SCRIPTS, library, para, record  # noqa: E402

sys.path.insert(0, SCRIPTS)
import build_character as bc  # noqa: E402
import summaries_owed  # noqa: E402
from library import Library  # noqa: E402

SET = os.path.join(SCRIPTS, '..', '..', 'wfrp-import', 'scripts', 'set_formulas.py')


class Owed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)
        rules = os.path.join(self.root, 'library-data', 'rules')
        with open(os.path.join(rules, 'soaked.json'), 'w') as f:
            json.dump({'slug': 'soaked', 'name': 'Soaked', 'source': 'LAMP', 'chapter': 'ch2', 'section': 'Soaked',
                       'page': 30, 'fields': {'kind': 'condition'}, 'content': [para('Wet through until dried by a fire.')]}, f)
        with open(os.path.join(rules, '_index.json')) as f: idx = json.load(f)
        idx.append({'slug': 'soaked', 'name': 'Soaked', 'source': 'LAMP', 'chapter': 'ch2', 'section': 'Soaked', 'page': 30,
                    'kind': 'condition'})
        with open(os.path.join(rules, '_index.json'), 'w') as f: json.dump(idx, f)
        self.rec = record(spells=[{'ref': 'spells/glow', 'how': 'free'}])
        self.rec['advances'] = [a for a in self.rec['advances'] if a.get('talent') != 'talents/far-sight']
        self.rec['advances'].append({'talent': 'talents/far-sight', 'specialisation': 'Ships', 'how': 'species'})
        self.rp = os.path.join(self.root, 'mara.json')
        with open(self.rp, 'w') as f: json.dump(self.rec, f)

    def tearDown(self):
        self.tmp.cleanup()

    def entry(self, cat, slug):
        return os.path.join(self.root, 'library-data', cat, slug + '.json')

    def owed(self):
        lib = Library(self.root, 'rock')
        return {(i['kind'], i['name']) for i in summaries_owed.owed(bc.build(self.rec, lib), lib)}

    def test_what_is_owed_and_what_isnt(self):
        got = self.owed()
        self.assertIn(('talent', 'Far Sight'), got)
        self.assertIn(('spell', 'Glow'), got)
        self.assertIn(('condition', 'Soaked'), got)
        subprocess.run([sys.executable, SET, self.entry('talents', 'far-sight'), '--specialisation', 'Gulls', '--summary', 'Counts gulls.'],
                       check=True, capture_output=True)
        self.assertIn(('talent', 'Far Sight (Ships)'), self.owed())        # summaries for some specialisations, not this one
        subprocess.run([sys.executable, SET, self.entry('talents', 'far-sight'), '--specialisation', 'Ships', '--summary', 'Names ships.'],
                       check=True, capture_output=True)
        subprocess.run([sys.executable, SET, self.entry('spells', 'glow'), '--summary', 'Lights a lamp.'], check=True, capture_output=True)
        got = self.owed()
        self.assertFalse({n for k, n in got if n.startswith('Far Sight')})
        self.assertNotIn(('spell', 'Glow'), got)
        self.assertIn(('condition', 'Soaked'), got)

    def test_the_listing_gives_the_file_the_command_and_the_text(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'summaries_owed.py'), self.rp, '--library', self.root,
                            '--campaign', 'rock'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('## Soaked (condition: no summary)', r.stdout)
        self.assertIn('library-data/rules/soaked.json (LAMP', r.stdout)
        self.assertIn('set_formulas.py "<library>/library-data/rules/soaked.json" --summary', r.stdout)
        self.assertIn('> Wet through until dried by a fire.', r.stdout)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'summaries_owed.py'), self.rp, '--library', self.root,
                            '--campaign', 'rock', '--no-text'], capture_output=True, text=True)
        self.assertNotIn('Wet through', r.stdout)

    def test_the_sheet_script_writes_the_markdown_sheet_too(self):
        out = os.path.join(self.root, 'out')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'character_pdf.py'), self.rp, '--library', self.root,
                            '--campaign', 'rock', '--out', out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        slug = bc.build(self.rec, Library(self.root, 'rock')).get('slug') or 'mara'
        with open(os.path.join(out, slug + '.md')) as f:
            self.assertEqual(f.read(), bc.markdown(bc.build(self.rec, Library(self.root, 'rock'))))
        self.assertTrue(os.path.exists(os.path.join(out, slug + '.html')))
        self.assertIn('still to write for the sheet', r.stdout)


if __name__ == '__main__':
    unittest.main()
