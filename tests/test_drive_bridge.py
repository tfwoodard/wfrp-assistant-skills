"""drive_bridge.py: Drive times kept from downloads, upload batches made from them, and checked."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'drive_bridge.py')
DEV = 'Q:\\Drive\\Lamps'


class Bridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.mirror, self.outputs, self.ledger = os.path.join(t, 'uploads', 'Lamps'), os.path.join(t, 'outputs'), os.path.join(t, 'ledger.json')
        os.makedirs(os.path.join(self.mirror, 'library-data', 'skills'))
        self.write('library-data/skills/rowing.json', '{"old": 1}')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = os.path.join(self.mirror, *rel.split('/'))
        with open(p, 'w') as f: f.write(text)
        return p

    def result(self, name, rows):
        p = os.path.join(self.tmp.name, name)
        with open(p, 'w') as f: json.dump({'staged': rows}, f)
        return p

    def run_(self, *args):
        return subprocess.run([sys.executable, SCRIPT, '--device-root', DEV, '--mirror', self.mirror, '--outputs', self.outputs,
                               '--ledger', self.ledger, '--wait', '0', *args], capture_output=True, text=True)

    def test_record_push_and_verify(self):
        dev = DEV + '\\library-data\\skills\\rowing.json'
        local = os.path.join(self.mirror, 'library-data', 'skills', 'rowing.json')
        r = self.run_('record', self.result('down.json', [{'devicePath': dev, 'stagedPath': local, 'mtimeMs': 111, 'bytes': 10, 'ok': True}]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.write('library-data/skills/rowing.json', '{"new": 2}')
        elsewhere = os.path.join(self.tmp.name, 'handoff.md')
        with open(elsewhere, 'w') as f: f.write('notes')
        self.assertIn('no Drive time recorded', self.run_('push', '--batch', 'b1', local, f'{elsewhere}=handoff.md').stderr)
        r = self.run_('push', '--batch', 'b1', local)
        self.assertEqual(r.returncode, 0, r.stderr)
        commit = json.loads(r.stdout.split('\n')[1])
        out = os.path.join(self.outputs, 'b1', 'library-data', 'skills', 'rowing.json')
        self.assertEqual(commit, [{'stagedPath': out, 'devicePath': dev, 'expectedMtimeMs': 111}])
        self.assertEqual(json.loads(r.stdout.split('\n')[3]), [dev])
        r = self.run_('push', '--batch', 'b2', '--new', f'{elsewhere}=handoff.md')
        self.assertEqual(json.loads(r.stdout.split('\n')[1]), [{'stagedPath': os.path.join(self.outputs, 'b2', 'handoff.md'),
                                                                  'devicePath': DEV + '\\handoff.md'}])
        # the upload went through: the download shows the new content
        ok = self.result('up.json', [{'devicePath': dev, 'stagedPath': local, 'mtimeMs': 222, 'bytes': 10, 'ok': True}])
        r = self.run_('verify', '--batch', 'b1', ok)
        self.assertEqual((r.returncode, r.stdout.splitlines()[0]), (0, '1 of 1 match'))
        with open(self.ledger) as f: self.assertEqual(json.load(f)[dev]['mtimeMs'], 222)
        # a stale upload: Drive still has the old content
        self.write('library-data/skills/rowing.json', '{"old": 1}')
        r = self.run_('verify', '--batch', 'b1', ok)
        self.assertEqual(r.returncode, 1)
        self.assertIn('Drive has something else', r.stdout)

    def test_a_file_outside_the_copy_needs_its_library_path(self):
        other = os.path.join(self.tmp.name, 'x.json')
        with open(other, 'w') as f: f.write('{}')
        self.assertIn('LOCAL=RELATIVE', self.run_('push', '--batch', 'b', other).stderr)
        self.assertIn('not a device_stage_files result', self.run_('record', other).stderr)


if __name__ == '__main__':
    unittest.main()
