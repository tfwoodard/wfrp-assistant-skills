"""The player skills are shared with any agent that reads the open Agent Skills format (claude.ai,
ChatGPT, the Gemini app, agents on a computer): keep them to the format, plain text, and free of
one agent's tool names."""
import os
import re
import subprocess
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

PLAYER = ['wfrp-rules-lookup', 'wfrp-character-sheet', 'wfrp-session-notes']
FRONTMATTER_KEYS = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'}
# one agent's machinery: a skill that says these only works there
ONE_AGENT = re.compile(r'mcp__|claude\.ai|\bdevice_(stage|commit|bash)|SendUserFile|present_files|'
                       r'\bClaude\b|\bCowork\b|Settings → Connectors|Google Drive connector', re.I)
# the library layout says how each agent reaches the library, so it names them
NAMES_AGENTS = {'references/library-layout.md'}


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    out = {}
    for line in (m.group(1) if m else '').splitlines():
        if re.match(r'^[A-Za-z-]+:', line):
            k, v = line.split(':', 1)
            out[k.strip()] = v.strip()
    return m, out


class AgentNeutralTest(unittest.TestCase):
    def test_frontmatter_is_the_open_format(self):
        for s in PLAYER:
            with self.subTest(skill=s):
                with open(os.path.join(ROOT, 'skills', s, 'SKILL.md'), encoding='utf-8') as f:
                    m, fm = frontmatter(f.read())
                self.assertIsNotNone(m, 'SKILL.md starts with YAML frontmatter')
                self.assertLessEqual(set(fm), FRONTMATTER_KEYS)
                self.assertEqual(fm['name'], s)                          # the folder's name
                self.assertRegex(fm['name'], r'^[a-z0-9]+(-[a-z0-9]+)*$')
                self.assertLessEqual(len(fm['name']), 64)
                self.assertTrue(0 < len(fm['description']) <= 1024)

    def test_no_one_agents_machinery(self):
        for s in PLAYER:
            base = os.path.join(ROOT, 'skills', s)
            for dirpath, _, files in os.walk(base):
                for n in files:
                    rel = os.path.relpath(os.path.join(dirpath, n), base).replace(os.sep, '/')
                    if rel in NAMES_AGENTS or '__pycache__' in rel:
                        continue
                    with open(os.path.join(dirpath, n), encoding='utf-8') as f:
                        text = f.read()
                    for i, line in enumerate(text.splitlines(), 1):
                        with self.subTest(file=f'{s}/{rel}', line=i):
                            self.assertIsNone(ONE_AGENT.search(line), line)

    def test_the_zips_are_one_folder_of_plain_text(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'package-skills.py')],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        for s in PLAYER:
            with self.subTest(skill=s), zipfile.ZipFile(os.path.join(ROOT, 'dist', 'players', s + '.zip')) as z:
                names = z.namelist()
                self.assertIn(f'{s}/SKILL.md', names)                    # one folder, SKILL.md in it
                self.assertTrue(all(n.startswith(s + '/') for n in names))
                for n in names:
                    self.assertTrue(n.endswith(('.md', '.py', '.json', '.txt', '.css', '.html')), n)
                    z.read(n).decode('utf-8')                            # plain text (Gemini takes no binaries)


if __name__ == '__main__':
    unittest.main()
