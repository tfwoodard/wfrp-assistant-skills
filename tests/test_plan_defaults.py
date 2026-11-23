"""plan_defaults.py and a plan's "defaults": a chapter's common kind and category written once."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts')
sys.path.insert(0, SCRIPTS)
import plan_defaults  # noqa: E402
from convert_rules import apply_defaults  # noqa: E402


class Defaults(unittest.TestCase):
    def test_apply_gives_what_an_entry_doesnt_say(self):
        plan = {'defaults': {'kind': 'condition'}, 'entries': [{'name': 'Soaked'}, {'name': 'Tide', 'kind': 'procedure'}]}
        self.assertEqual([e['kind'] for e in apply_defaults(plan)['entries']], ['condition', 'procedure'])
        self.assertEqual(apply_defaults({'entries': [{'name': 'x'}]}), {'entries': [{'name': 'x'}]})
        with self.assertRaises(SystemExit):
            apply_defaults({'defaults': {'page': 3}, 'entries': []})

    def test_a_lore_chapter_gets_both(self):
        plan = {'source': 'LAMP', 'chapter': 'ch9', 'entries': [
            {'name': 'Gull Rock', 'page': 1, 'category': 'lore', 'kind': 'place'},
            {'name': 'North Pier', 'page': 2, 'category': 'lore', 'kind': 'place'},
            {'name': 'The Keeper', 'page': 3, 'category': 'lore', 'kind': 'god'},
            {'name': 'Lighting Up', 'page': 4}]}                              # a rules procedure, by the converter's fallback
        new, said = plan_defaults.compact(plan)
        self.assertEqual(new['defaults'], {'category': 'lore', 'kind': 'place'})
        self.assertEqual(list(new)[:3], ['source', 'chapter', 'defaults'])
        self.assertEqual(new['entries'], [{'name': 'Gull Rock', 'page': 1}, {'name': 'North Pier', 'page': 2},
                                          {'name': 'The Keeper', 'page': 3, 'kind': 'god'},
                                          {'name': 'Lighting Up', 'page': 4, 'category': 'rules', 'kind': 'procedure'}])
        self.assertEqual([plan_defaults.meaning(e) for e in apply_defaults(new)['entries']],
                         [plan_defaults.meaning(e) for e in plan['entries']])

    def test_defaults_that_save_only_their_own_line_arent_set(self):
        plan = {'entries': [{'name': 'Gull Rock', 'page': 1, 'category': 'lore', 'kind': 'place'}]}
        new, said = plan_defaults.compact(plan)
        self.assertIsNone(new)
        self.assertIn('not worth it', said)

    def test_an_entry_with_no_kind_at_all_blocks_a_kind_default(self):
        plan = {'entries': [{'name': 'Rowing', 'category': 'skills'}, {'name': 'Steady', 'category': 'talents'},
                            {'name': 'A', 'kind': 'other'}, {'name': 'B', 'kind': 'other'}, {'name': 'C', 'kind': 'other'}]}
        new, said = plan_defaults.compact(plan)
        self.assertIsNone(new)
        self.assertIn('no kind default: 2 entries have no kind at all', said)

    def test_the_command_writes_in_the_plans_layout(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'ch5.json')
            plan = {'source': 'LAMP', 'chapter': 'ch5', 'entries': [{'name': n, 'page': 1, 'kind': 'condition'} for n in 'ABC']}
            with open(p, 'w') as f: f.write(json.dumps(plan, indent=1) + '\n')
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'plan_defaults.py'), p], capture_output=True, text=True)
            self.assertIn("kind 'condition': 3 keys fewer", r.stdout)
            with open(p) as f: self.assertEqual(json.load(f), plan)                # a dry run writes nothing
            subprocess.run([sys.executable, os.path.join(SCRIPTS, 'plan_defaults.py'), p, '--write'], check=True, capture_output=True)
            with open(p) as f: raw = f.read()
            self.assertEqual(json.loads(raw)['defaults'], {'kind': 'condition'})
            self.assertTrue(raw.startswith('{\n "source"'))                         # still an indent of 1
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'plan_defaults.py'), p], capture_output=True, text=True)
            self.assertIn('has defaults already', r.stdout)
            hand = os.path.join(d, 'ch6.json')                                     # laid out by hand
            with open(hand, 'w') as f:
                f.write('{"source": "LAMP", "chapter": "ch6",\n "entries": [' + ',\n  '.join(
                    json.dumps({'name': n, 'page': 1, 'kind': 'condition'}) for n in 'ABC') + ']}\n')
            with open(hand) as f: before = f.read()
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'plan_defaults.py'), hand, '--write'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('not written', r.stdout)
            with open(hand) as f: self.assertEqual(f.read(), before)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, 'plan_defaults.py'), hand, '--write', '--reformat'], check=True, capture_output=True)
            with open(hand) as f: self.assertEqual(json.load(f)['defaults'], {'kind': 'condition'})


if __name__ == '__main__':
    unittest.main()
