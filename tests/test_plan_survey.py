"""plan_survey.py: what the plans tell the converters, from invented plans and entries."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'plan_survey.py')
sys.path.insert(0, os.path.dirname(SCRIPT))
import plan_survey  # noqa: E402


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: json.dump(data, f)


class Survey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = self.tmp.name
        write(f'{r}/library-data/rules/_index.json', [{'slug': 'soaked', 'name': 'Soaked', 'source': 'LAMP'},
                                                      {'slug': 'dazed', 'name': 'Dazed', 'source': 'LAMP'}])
        write(f'{r}/library-data/rules/soaked.json', {'content': [{'type': 'paragraph', 'text': 'Unlike most, Soaked does not stack.'}]})
        write(f'{r}/library-data/rules/dazed.json', {'content': [{'type': 'paragraph', 'text': 'The bonus does not increase.'}]})
        write(f'{r}/library-data/skills/_index.json', [{'slug': 'rowing', 'name': 'Rowing', 'source': 'LAMP'}])
        write(f'{r}/library-data/skills/rowing.json', {'content': [{'type': 'paragraph', 'text': 'Rowing (S) Advanced'}]})
        write(f'{r}/sources/LAMP/plans/ch2.json', {
            'source': 'LAMP', 'chapter': 'ch2', 'scheme_columns': {'ws': 'WS', 'bs': 'BS'}, 'intro': {'name': 'Rules', 'kind': 'other'},
            'boxes': {'3.1': {'to': 'Soaked'}, '4.1': {'diagram': 'x'}}, 'moon_phase': 'full',
            'entries': [{'name': 'Soaked', 'page': 3, 'kind': 'condition', 'fields': {'stacks': False}},
                        {'name': 'Dazed', 'page': 3, 'kind': 'condition', 'fields': {'stacks': False}},
                        {'name': 'Mopping', 'page': 4, 'kind': 'procedure', 'stat_blocks': 1},
                        {'name': 'Rowing', 'page': 5, 'kind': 'condition', 'category': 'skills',
                         'fields': {'characteristic': 'S', 'advanced': True}},
                        {'name': 'Lost Oar', 'page': 6, 'kind': 'condition', 'category': 'skills', 'fields': {'enc': 1}}],
            'relations': {'skills/rowing-boats': [{'role': 'adds-to', 'to': 'skills/rowing'}],
                          'rules/soaked-pier': [{'role': 'distinct-from', 'to': 'rules/soaked'}],
                          'rules/wet': [{'role': 'adds-to', 'to': 'rules/soaked'}]}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_groups_signals_and_what_is_left(self):
        s = plan_survey.survey(self.root)
        rows = {(r['group'], r['kind']): r for r in s['rows']}
        self.assertEqual((rows[('facts', 'field stacks')]['items'], rows[('facts', 'field stacks')]['accounted']), (2, 1))
        self.assertIn('Dazed', rows[('facts', 'field stacks')]['examples'][0])         # "does not increase" isn't "does not stack"
        self.assertEqual(rows[('facts', 'field characteristic')]['accounted'], 1)
        self.assertEqual(rows[('facts', 'field advanced')]['accounted'], 1)
        self.assertEqual(rows[('facts', 'relation adds-to')]['accounted'], 1)             # rowing-boats, not wet
        self.assertEqual(rows[('facts', 'relation distinct-from')]['accounted'], 1)
        self.assertEqual(rows[('map', 'entry kind')]['accounted'], 4)                     # the chapter's most common
        self.assertEqual(rows[('layout', 'scheme_columns')]['items'], 1)                  # one per plan, not per column
        self.assertEqual(rows[('layout', 'boxes')]['items'], 2)
        self.assertEqual(rows[('layout', 'entry stat_blocks')]['items'], 1)
        self.assertEqual(s['unclassified'], {'moon_phase (plan)': 1})                      # said, not skipped
        self.assertEqual(s['entries_not_read'], ['sources/LAMP/plans/ch2.json: Lost Oar (p. 6)'])

    def test_the_report(self):
        r = subprocess.run([sys.executable, SCRIPT, '--library', self.root], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('# What the plans tell the converters (1 plans)', r.stdout)
        self.assertIn('## Unclassified plan keys', r.stdout)
        self.assertIn('moon_phase (plan): 1', r.stdout)
        self.assertLess(r.stdout.index('| map | entry (heading is an entry) | 5'), r.stdout.index('| facts | field stacks |'))


if __name__ == '__main__':
    unittest.main()
