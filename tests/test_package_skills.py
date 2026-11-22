"""package-skills.py: reproducible zips, and which ones changed since the manifest in Drive."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('package_skills', os.path.join(ROOT, 'scripts', 'package-skills.py'))
pk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pk)


class PackageTest(unittest.TestCase):
    def test_every_skill_is_assigned_and_the_librarians_are_never_packaged(self):
        self.assertEqual(set(os.listdir(os.path.join(ROOT, 'skills'))), set(pk.PLAYERS + pk.GM + pk.LIBRARIAN))
        with tempfile.TemporaryDirectory() as d:
            m = pk.package(d)
            names = set().union(*(set(x['zips']) for x in m.values()))
            self.assertEqual(names, {s + '.zip' for s in pk.PLAYERS + pk.GM})
            for folder in m:
                self.assertTrue(os.path.exists(os.path.join(d, folder, 'README.md')))

    def test_zips_are_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(pk.package(a), pk.package(b))

    def test_compare_and_collect(self):
        with tempfile.TemporaryDirectory() as d:
            m = pk.package(os.path.join(d, 'dist'))['players']
            same = os.path.join(d, 'same.json')
            with open(same, 'w') as f:
                json.dump(m, f)
            self.assertEqual(pk.changed_zips(m, same), ([], m['version']))
            old = dict(m, version='0.0.1', zips=dict(m['zips'], **{'wfrp-rules-lookup.zip': 'x'}))
            older = os.path.join(d, 'old.json')
            with open(older, 'w') as f:
                json.dump(old, f)
            self.assertEqual(pk.changed_zips(m, older), (['wfrp-rules-lookup.zip'], '0.0.1'))
            self.assertEqual(pk.changed_zips(m, os.path.join(d, 'none.json')), (list(m['zips']), None))
            up = os.path.join(d, 'up')
            names = pk.collect(os.path.join(d, 'dist'), 'players', ['wfrp-rules-lookup.zip'], up)
            self.assertEqual(sorted(os.listdir(os.path.join(up, 'players'))), sorted(names))
            self.assertEqual(sorted(names), ['README.md', 'manifest.json', 'wfrp-rules-lookup.zip'])
            self.assertEqual(pk.collect(os.path.join(d, 'dist'), 'players', [], up), [])
            self.assertFalse(os.path.exists(os.path.join(up, 'players')))

    def test_the_command_line_refuses_an_unknown_folder(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'package-skills.py'), '--compare', 'dm=x.json'],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('players=<manifest> or gm=<manifest>', r.stderr)


if __name__ == '__main__':
    unittest.main()
