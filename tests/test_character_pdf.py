"""character_pdf.py: the printed sheet, from an invented library."""
import copy
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_character import SCRIPTS, library, record  # noqa: E402

sys.path.insert(0, SCRIPTS)
import build_character as bc  # noqa: E402
import character_pdf  # noqa: E402
from library import Library  # noqa: E402


class Sheet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def model(self, **over):
        return bc.build(record(**over), Library(self.root, 'rock'))

    def test_everything_the_build_reports_is_on_the_sheet(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2}], details={'age': 31, 'eyes': 'Grey'},
                   ambitions={'short': 'Mend the lamp'}, money={'gc': 1, 'ss': 2, 'd': 3},
                   trappings=[{'id': 'bag', 'name': 'Satchel', 'enc': 1}, {'ref': 'trappings/boat-hook', 'in': 'bag'}],
                   exceptions=[{'id': 'level-complete:warden/1', 'why': 'the GM moved her on'}],
                   incomplete=['Her oath to the harbour'])
        r['advances'].append({'skill': 'skills/watch', 'count': 1, 'how': 'xp', 'xp': 99})
        html = character_pdf.document(bc.build(r, Library(self.root, 'rock')))
        for s in ('Mara', 'Keepers', 'Warden 2', 'Initiative', 'Wounds', 'Walk', 'Basic skills', 'Talents', 'Far Sight',
                  'Still to complete', 'Accepted differences', 'the GM moved her on', 'Differs from the rules', 'xp-cost:',
                  'To settle', 'Her oath to the harbour', 'Satchel', '└ Boat Hook', 'Weapons', 'Damage', '1 gc', 'Mend the lamp',
                  'Age <b>31</b>', 'Eyes <b>Grey</b>', 'Not worked out'):
            self.assertIn(s, html, s)
        self.assertEqual(html.count('class="page'), 2)

    def test_text_from_the_record_is_escaped(self):
        html = character_pdf.document(self.model(name='<Mara & Co>'))
        self.assertIn('&lt;Mara &amp; Co&gt;', html)
        self.assertNotIn('<Mara', html)

    @unittest.skipUnless(character_pdf.find_browser(), 'no browser to print with')
    def test_the_pdf_prints_on_two_pages(self):
        import json
        p = os.path.join(self.root, 'mara.json')
        with open(p, 'w') as f: json.dump(record(), f)
        out = os.path.join(self.root, 'out')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'character_pdf.py'), p, '--library', self.root, '--campaign', 'rock',
                            '--out', out, '--pdf'], capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(out, 'mara.pdf'), 'rb') as f:
            self.assertEqual(len(re.findall(rb'/Type\s*/Page(?!s)', f.read())), 2)


if __name__ == '__main__':
    unittest.main()
