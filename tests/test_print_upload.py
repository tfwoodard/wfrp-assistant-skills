"""Tests for skills/wfrp-import/scripts/print_upload.py (invented text only).

Run: python3 -m unittest discover tests
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'print_upload.py')


def run(*args):
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def bodies(out):
    """Rebuild each file's text from printed parts: {name: text}."""
    got = {}
    for m in re.finditer(r'=== BEGIN (\S+) \| part \d+/\d+ .*?ends with newline: (yes|no) ===\n'
                         r'(.*?)=== END \1', out, re.S):
        got.setdefault(m.group(1), []).append((m.group(3), m.group(2)))
    return {k: ''.join(b for b, _ in v)[:None if v[-1][1] == 'yes' else -1] for k, v in got.items()}


class PrintUploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        return path

    def test_small_files_share_a_part_and_round_trip(self):
        a = self.write('a.md', '# Quokka\n\nSmiles a lot.\n')
        b = self.write('b.json', '{"x": 1}')
        code, out, _ = run(a, b)
        self.assertEqual(code, 0)
        self.assertIn('a.md | part 1/1 | lines 1-3 of 3 | 24 bytes | ends with newline: yes', out)
        self.assertIn('b.json | part 1/1 | lines 1-1 of 1 | 8 bytes | ends with newline: no', out)
        self.assertIn('print part 1 of 1; that was the last part', out)
        self.assertEqual(bodies(out), {'a.md': '# Quokka\n\nSmiles a lot.\n', 'b.json': '{"x": 1}'})

    def test_large_file_splits_at_lines_and_parts_join_exactly(self):
        text = ''.join(f'  {{"slug": "beast-{i:03}", "note": "é"}},\n' for i in range(200))
        path = self.write('_index.json', text)
        code, out, _ = run(path, '--list', '--max-chars', '2000')
        self.assertEqual(code, 0)
        n = int(re.search(r'(\d+) print part\(s\)', out).group(1))
        self.assertGreater(n, 1)
        self.assertIn(f'{len(text.encode("utf-8"))} bytes', out)
        printed = ''
        for k in range(1, n + 1):
            code, part, _ = run(path, '--max-chars', '2000', '--part', str(k))
            self.assertEqual(code, 0)
            self.assertLessEqual(len(part), 2000 + 400)
            printed += part
        self.assertEqual(bodies(printed)['_index.json'], text)

    def test_bad_part_number(self):
        path = self.write('a.md', 'x\n')
        code, _, err = run(path, '--part', '3')
        self.assertEqual(code, 2)
        self.assertIn('--part must be 1..1', err)


if __name__ == '__main__':
    unittest.main()
