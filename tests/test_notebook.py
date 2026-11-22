"""notebook.py: the campaign notebook, and its current notes on the sheets."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_character import SCRIPTS, library, record  # noqa: E402

sys.path.insert(0, SCRIPTS)
import build_character as bc  # noqa: E402
import character_pdf  # noqa: E402
import notebook  # noqa: E402
from library import Library  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Notebook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)
        self.cdir = os.path.join(self.root, 'campaigns', 'rock')

    def tearDown(self):
        self.tmp.cleanup()

    def nb(self, *args, gm=False):
        return subprocess.run([sys.executable, os.path.join(ROOT, 'shared', 'scripts', 'notebook.py'), self.cdir,
                               *(['--gm'] if gm else []), *args], capture_output=True, text=True)

    def test_add_edit_retire_restore_and_list(self):
        r = self.nb('add', '--kind', 'npc', '--name', 'Oss the Ferryman', '--text', 'Rows the night crossing; owes Mara a favour',
                    '--from', 'history')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("a note 'oss-the-ferryman' already", self.nb('add', '--kind', 'npc', '--name', 'Oss the ferryman', '--text', 'x').stderr)
        self.nb('add', '--kind', 'item', '--name', 'Brass Key', '--text', 'Opens the lamp room', '--from', '3', '--for', 'mara')
        self.nb('add', '--kind', 'fact', '--name', 'Gull omen', '--text', 'Gulls inland mean a storm')
        self.assertIn("--from takes", self.nb('add', '--kind', 'fact', '--name', 'X', '--text', 'y', '--from', 'soon').stderr)
        self.assertEqual(self.nb('retire', 'gull-omen', '--session', '5', '--why', 'the storm came').returncode, 0)
        notes = notebook.load(self.cdir)
        self.assertEqual([n['id'] for n in notes], ['oss-the-ferryman', 'brass-key', 'gull-omen'])   # retired, but kept
        self.assertEqual(notes[0]['from'], 'history')
        self.assertEqual(notes[1]['from'], 3)
        self.assertEqual(notes[2]['retired']['session'], 5)
        self.assertEqual([n['id'] for n in notebook.current(notes, 'mara')], ['oss-the-ferryman', 'brass-key'])
        self.assertEqual([n['id'] for n in notebook.current(notes, 'oss')], ['oss-the-ferryman'])    # not Mara's key
        self.assertIn('retired s5: the storm came', self.nb('list', '--retired').stdout)
        self.nb('edit', 'brass-key', '--party')
        self.nb('restore', 'gull-omen')
        self.assertEqual(len(notebook.current(notebook.load(self.cdir), 'oss')), 3)
        self.assertIn("isn't retired", self.nb('restore', 'gull-omen').stderr)
        self.nb('add', '--kind', 'npc', '--name', 'The Hooded One', '--text', 'Is the cult leader', gm=True)
        self.assertTrue(os.path.exists(os.path.join(self.cdir, 'gm', 'notes.json')))
        self.assertNotIn('Hooded', json.dumps(notebook.load(self.cdir)))

    def test_the_sheets_show_what_is_current_for_that_character(self):
        notebook.save(self.cdir, [
            {'id': 'oss', 'kind': 'npc', 'name': 'Oss', 'text': 'Rows the night crossing', 'from': None},
            {'id': 'key', 'kind': 'item', 'name': 'Brass Key', 'text': 'Opens the lamp room', 'from': 3, 'for': 'mara'},
            {'id': 'pin', 'kind': 'item', 'name': 'Silver Pin', 'text': "Someone else's", 'from': 3, 'for': 'oss'},
            {'id': 'omen', 'kind': 'fact', 'name': 'Gull omen', 'text': 'Gulls inland mean a storm', 'from': 2,
             'retired': {'session': 5, 'date': '2026-11-01'}}])
        notebook.save(self.cdir, [{'id': 'hood', 'kind': 'npc', 'name': 'The Hooded One', 'text': 'Cult leader', 'from': None}], gm=True)
        m = bc.build(record(), Library(self.root, 'rock'))
        self.assertEqual([n['name'] for n in m['remember']], ['Oss', 'Brass Key'])
        play = character_pdf.document(m)
        play = play[play.index('class="page new play"'):]
        self.assertIn('<h2>Remember</h2>', play)
        self.assertLess(play.index('Oss'), play.index('Brass Key'))           # the party's first
        for s in ('Silver Pin', 'Gull omen', 'Hooded'):
            self.assertNotIn(s, play, s)
        md = bc.markdown(m)
        self.assertIn('- Brass Key (item): Opens the lamp room', md[md.index('## Remember'):])
        self.assertNotIn('remember', bc.build(record(), Library(self.root)))  # no campaign, no notebook


if __name__ == '__main__':
    unittest.main()
