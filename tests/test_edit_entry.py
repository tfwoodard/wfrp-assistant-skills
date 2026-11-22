"""edit_entry.py: one entry's fields and relations changed in its .json, .md, index line and plan."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'edit_entry.py')


class EditEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        d = os.path.join(self.root, 'library-data', 'skills')
        os.makedirs(d)
        self.entry = {'slug': 'tide-lore', 'name': 'Lore (Tides)', 'source': 'LAMP', 'chapter': 'ch3', 'section': 'Lore (Tides)',
                      'page': 7, 'fields': {}, 'content': [{'type': 'paragraph', 'text': 'Knowing when the water turns.'}]}
        with open(os.path.join(d, 'tide-lore.json'), 'w') as f: json.dump(self.entry, f)
        recs = [{'slug': 'lore', 'name': 'Lore', 'source': 'LAMP', 'page': 5, 'characteristic': 'Int', 'advanced': True, 'edition': '4e'},
                {'slug': 'tide-lore', 'name': 'Lore (Tides)', 'source': 'LAMP', 'page': 7, 'edition': '4e'},
                {'slug': 'rowing', 'name': 'Rowing', 'source': 'LAMP', 'page': 8, 'characteristic': 'S', 'edition': '4e'}]
        self.index = '[\n' + ',\n'.join('  ' + json.dumps(r) for r in recs) + '\n]\n'
        with open(os.path.join(d, '_index.json'), 'w') as f: f.write(self.index)
        os.makedirs(os.path.join(self.root, 'sources', 'LAMP', 'plans'))
        self.plan = {'source': 'LAMP', 'chapter': 'ch3', 'entries': [{'category': 'skills', 'name': 'Lore (Tides)', 'page': 7},
                                                                      {'name': 'Tides', 'page': 9}], 'relations': {}}
        self.plan_raw = json.dumps(self.plan, indent=0)
        with open(self.path('sources/LAMP/plans/ch3.json'), 'w') as f: f.write(self.plan_raw)

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, rel):
        return os.path.join(self.root, *rel.split('/'))

    def run_(self, *args):
        return subprocess.run([sys.executable, SCRIPT, '--library', self.root, *args], capture_output=True, text=True)

    def read(self, rel):
        with open(self.path(rel), encoding='utf-8') as f: return f.read()

    def test_fields_and_a_relation_reach_the_entry_its_page_its_index_line_and_the_plan(self):
        r = self.run_('skills/tide-lore', '--set', 'characteristic=Int', '--set', 'advanced=true', '--set', 'grouped=false',
                      '--relation', 'adds-to:skills/lore', '--plan', 'sources/LAMP/plans/ch3.json')
        self.assertEqual(r.returncode, 0, r.stderr)
        e = json.loads(self.read('library-data/skills/tide-lore.json'))
        self.assertEqual(e['fields'], {'characteristic': 'Int', 'advanced': True, 'grouped': False})
        self.assertEqual(e['relations'], [{'role': 'adds-to', 'to': 'skills/lore'}])
        self.assertIn('characteristic: Int', self.read('library-data/skills/tide-lore.md'))
        old, new = self.index.split('\n'), self.read('library-data/skills/_index.json').split('\n')
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, new)) if a != b], [2])     # only that line
        rec = json.loads(new[2].strip().rstrip(','))
        self.assertEqual((rec['characteristic'], rec['advanced'], rec['grouped'], rec['relations'], list(rec)[-1]),
                         ('Int', True, False, [{'role': 'adds-to', 'to': 'skills/lore'}], 'edition'))
        plan_raw = self.read('sources/LAMP/plans/ch3.json')
        plan = json.loads(plan_raw)
        self.assertEqual(plan['entries'][0]['fields'], {'characteristic': 'Int', 'advanced': True, 'grouped': False})
        self.assertEqual(plan['relations'], {'skills/tide-lore': [{'role': 'adds-to', 'to': 'skills/lore'}]})
        self.assertEqual(plan_raw, json.dumps(plan, indent=0))                              # its layout kept

    def test_unset_and_no_relation_take_things_off_and_dry_run_writes_nothing(self):
        self.run_('skills/tide-lore', '--set', 'characteristic=Int', '--relation', 'adds-to:skills/lore')
        r = self.run_('skills/tide-lore', '--unset', 'characteristic', '--no-relation', 'adds-to:skills/lore', '--dry-run')
        self.assertIn('would write', r.stdout)
        self.assertEqual(json.loads(self.read('library-data/skills/tide-lore.json'))['fields'], {'characteristic': 'Int'})
        self.run_('skills/tide-lore', '--unset', 'characteristic', '--no-relation', 'adds-to:skills/lore')
        e = json.loads(self.read('library-data/skills/tide-lore.json'))
        self.assertEqual((e['fields'], 'relations' in e), ({}, False))
        self.assertEqual(self.read('library-data/skills/_index.json'), self.index)          # back as it was

    def test_formulas_bad_relations_and_missing_entries_are_refused(self):
        self.assertIn('set_formulas.py', self.run_('skills/tide-lore', '--set', 'summary=Knows tides').stderr)
        self.assertIn('ROLE:category/slug', self.run_('skills/tide-lore', '--relation', 'likes:skills/lore').stderr)
        self.assertIn("isn't there", self.run_('skills/sea-lore', '--set', 'advanced=true').stderr)
        self.assertNotEqual(self.run_('skills/tide-lore', '--set', 'advanced').returncode, 0)


if __name__ == '__main__':
    unittest.main()
