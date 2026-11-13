"""Tests for check_names.py, on invented entries."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'skills', 'wfrp-import', 'scripts'))
from check_names import check, name_key  # noqa: E402


class CheckNamesTest(unittest.TestCase):
    def test_names_match_across_plurals_brackets_and_punctuation(self):
        self.assertEqual(name_key('Lamplighter!'), name_key('Lamplighters'))
        self.assertEqual(name_key('The Wick (Hemp)'), name_key('wick'))

    def test_a_shared_name_needs_a_relation(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'careers'))
            with open(os.path.join(d, 'careers', '_index.json'), 'w') as f:
                json.dump([{'slug': 'lamplighter', 'name': 'Lamplighter'}], f)
            recs = os.path.join(d, '_records.json')
            with open(recs, 'w') as f:
                json.dump([
                    {'_category': 'talents', 'slug': 'lamplighter', 'name': 'Lamplighter!'},
                    {'_category': 'talents', 'slug': 'wick-sense', 'name': 'Wick Sense (Hemp)'},
                    {'_category': 'skills', 'slug': 'wick-sense', 'name': 'Wick Sense',
                     'relations': [{'role': 'distinct-from', 'to': 'talents/wick-sense'}]},
                ], f)
            missing, decided = check(d, [recs])
            self.assertEqual(missing, [('talents/lamplighter', 'careers/lamplighter')])
            self.assertEqual(decided, [('skills/wick-sense', 'talents/wick-sense')])


if __name__ == '__main__':
    unittest.main()
