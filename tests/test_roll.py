"""roll.py: rolls on the library's tables and dice, on an invented library."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_character import SCRIPTS, library  # noqa: E402

sys.path.insert(0, SCRIPTS)
import roll  # noqa: E402


class Roll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, *args):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'roll.py'), '--library', self.root, '--campaign', 'rock', *args],
                           capture_output=True, text=True)
        return r

    def js(self, *args):
        r = self.run_(*args, '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_ranges_read_as_printed(self):
        self.assertEqual([roll.span(c, 100) for c in ('01–03', '98–00', '05', '100', '–', 'Warden')],
                         [(1, 3), (98, 100), (5, 5), (100, 100), None, None])

    def test_a_column_per_species_needs_one_and_blank_cells_repeat_the_one_above(self):
        self.assertIn('Give --column', self.run_('table', 'Random Callings').stderr)
        out = self.js('table', 'Random Callings', '--column', 'Keeper', '--result', '75')
        self.assertEqual((out['column'], out['row']), ('Keepers', {'Class': 'WATCHERS', 'Calling': 'Lamplighter'}))
        out = self.js('table', 'random-callings', '--column', 'Marsh Folk', '--result', '100')
        self.assertEqual(out['row'], {'Class': 'RIVERMEN', 'Calling': 'Ferryman'})
        self.assertIn("did you mean", self.run_('table', 'Callings').stderr)

    def test_the_tables_own_dice_are_rolled_and_shown(self):
        out = self.js('table', 'Random Callings', '--column', 'Keepers', '--seed', '1')
        self.assertTrue(1 <= out['roll'] <= 100)
        self.assertIn('rolled d100', out['said'][-1])
        self.assertIsNotNone(out['row'])

    def test_dice_and_characteristics(self):
        out = self.js('dice', '2d10+3', '--seed', '4')
        self.assertEqual(out['total'], sum(out['dice'][0]['dice']) + 3)
        self.assertEqual(len(out['dice'][0]['dice']), 2)
        ch = self.js('characteristics', '--species', 'Keepers', '--seed', '2')['rolls']
        self.assertEqual([c['code'] for c in ch], ['WS', 'BS', 'S', 'T', 'I', 'Ag', 'Dex', 'Int', 'WP', 'Fel'])
        self.assertTrue(all(c['value'] == c['rolled'] + 23 and 2 <= c['rolled'] <= 20 for c in ch))
        text = self.run_('characteristics', '--species', 'Keepers', '--seed', '2').stdout
        self.assertIn('initial WS=', text)
        self.assertIn('--how rolled', text)


if __name__ == '__main__':
    unittest.main()
