"""Tests for skills/wfrp-import/scripts/compare_download.py.

Run: python3 -m unittest discover tests
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'compare_download.py')
TEXT = '---\nslug: quillback\ntags: [hedge]\n---\n\nQuillbacks roll downhill’s way.\n'


class CompareDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local = self.write('local.md', TEXT)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = os.path.join(self.tmp.name, name)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)
        return p

    def run_it(self, download, *extra):
        return subprocess.run([sys.executable, SCRIPT, self.local, download, *extra],
                              capture_output=True, text=True)

    def b64(self, text):
        return base64.b64encode(text.encode('utf-8')).decode()

    def test_every_download_form_matches(self):
        for name, content in (('raw.md', TEXT), ('content.b64', self.b64(TEXT)),
                              ('result.json', json.dumps({'id': 'X', 'content': self.b64(TEXT)}))):
            r = self.run_it(self.write(name, content))
            self.assertEqual(r.returncode, 0, name + r.stdout + r.stderr)
            self.assertIn('Identical', r.stdout)

    def test_a_slip_is_shown(self):
        r = self.run_it(self.write('bad.b64', self.b64(TEXT.replace('downhill', 'down hill'))))
        self.assertEqual(r.returncode, 1)
        self.assertIn('DIFFERENT', r.stdout)
        self.assertIn('+Quillbacks roll down hill', r.stdout)

    def test_original_lists_the_intended_changes(self):
        orig = self.write('orig.md', TEXT.replace('tags: [hedge]', 'tags: []'))
        r = self.run_it(self.write('ok.md', TEXT), '--original', orig)
        self.assertEqual(r.returncode, 0)
        self.assertIn('changed 2 line(s)', r.stdout)
        self.assertIn('-tags: []', r.stdout)
        self.assertIn('+tags: [hedge]', r.stdout)


if __name__ == '__main__':
    unittest.main()
