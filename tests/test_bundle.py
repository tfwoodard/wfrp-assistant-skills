"""bundle.py: the library's rules data in one file, for agents whose scripts can't see Drive.

The library here is invented."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), 'shared', 'scripts', 'bundle.py')
sys.path.insert(0, os.path.dirname(SCRIPT))
import bundle  # noqa: E402

FILES = {
    'library.json': json.dumps({'wfrp_library': True, 'layout_version': 1, 'name': 'Lantern Library',
                                'sources': [{'code': 'LAMP'}]}, indent=2) + '\n',
    'library-data/_import-log.json': json.dumps([{'source': 'LAMP', 'chapter': 'ch1'}, {'source': 'LAMP', 'chapter': 'ch2'}]),
    'library-data/rules/_index.json': '[\n  {"slug": "wick-rot", "name": "Wick Rot"}\n]\n',
    'library-data/rules/wick-rot.json': json.dumps({'slug': 'wick-rot', 'name': 'Wick Rot'}),
    'library-data/rules/wick-rot.md': '# Wick Rot\n\nA damp wick smoulders.\n',
    'campaigns/glow/campaign.json': '{"slug": "glow"}',
    'campaigns/glow/gm/notes.json': '{"notes": [{"text": "the lamplighter is the thief"}]}',
}


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, 'library')
        for rel, text in FILES.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, *p):
        with open(os.path.join(*p), encoding='utf-8') as f:
            return f.read()

    def test_make_and_unpack_give_the_rules_data_and_nothing_from_campaigns(self):
        out, stamp = bundle.make(self.root)
        self.assertEqual(out, os.path.join(self.root, 'library-bundle.json'))
        self.assertEqual(stamp['imports'], 2)
        said = self.read(out)
        self.assertNotIn('lamplighter', said)                       # gm/ never goes in
        self.assertNotIn('campaigns/', said)
        lib = json.loads(self.read(self.root, 'library.json'))
        self.assertEqual(lib['bundle'], stamp)                       # the stamp, in the library's library.json
        before = FILES['library.json'].split('\n')
        after = self.read(self.root, 'library.json').split('\n')
        self.assertEqual([l for l in after if not l.startswith('  "bundle": ')], before)  # one line added, no other change
        bundle.make(self.root)
        again = self.read(self.root, 'library.json').split('\n')
        self.assertEqual(len(again), len(after))                      # a second make replaces that line
        dest = os.path.join(self.tmp.name, 'lib')
        n = bundle.unpack(out, dest)
        self.assertEqual(n, stamp['files'])
        for rel in ('library-data/rules/wick-rot.json', 'library-data/rules/wick-rot.md',
                    'library-data/rules/_index.json', 'library-data/_import-log.json'):
            self.assertEqual(self.read(dest, rel), self.read(self.root, rel))
        self.assertEqual(self.read(dest, 'library.json'), self.read(self.root, 'library.json'))
        self.assertFalse(os.path.exists(os.path.join(dest, 'campaigns')))

    def test_check_says_when_the_bundle_is_out_of_date(self):
        out, stamp = bundle.make(self.root)
        lj = os.path.join(self.root, 'library.json')
        ok, said = bundle.check(out, lj)
        self.assertTrue(ok, said)
        old = os.path.join(self.tmp.name, 'old-bundle.json')
        os.rename(out, old)
        import datetime
        bundle.make(self.root, now=datetime.datetime(2031, 1, 2, tzinfo=datetime.timezone.utc))
        ok, said = bundle.check(old, lj)
        self.assertFalse(ok)
        self.assertIn('out of date', said)
        ok, said = bundle.check(old, json.dumps({'wfrp_library': True}))  # library.json text, no stamp yet
        self.assertFalse(ok)
        self.assertIn('no bundle stamp', said)

    def test_unpack_refuses_a_file_outside_the_folder_or_from_campaigns(self):
        for bad in ('../escape.json', 'campaigns/glow/gm/notes.json'):
            path = os.path.join(self.tmp.name, 'bad.json')
            with open(path, 'w') as f:
                json.dump({'wfrp_library_bundle': 1, 'stamp': {}, 'files': {bad: '{}'}}, f)
            with self.assertRaises(SystemExit):
                bundle.unpack(path, os.path.join(self.tmp.name, 'x'))

    def test_the_command_line(self):
        r = subprocess.run([sys.executable, SCRIPT, 'make', self.root], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('upload both', r.stdout)
        b = os.path.join(self.root, 'library-bundle.json')
        r = subprocess.run([sys.executable, SCRIPT, 'check', b, os.path.join(self.root, 'library.json')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        r = subprocess.run([sys.executable, SCRIPT, 'unpack', b, os.path.join(self.tmp.name, 'lib')], capture_output=True, text=True)
        self.assertIn('--library', r.stdout)


if __name__ == '__main__':
    unittest.main()
