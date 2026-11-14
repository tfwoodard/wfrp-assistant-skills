"""Tests for render_entry.py (invented entries).

Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts'))
from render_entry import render  # noqa: E402


class RenderEntryTest(unittest.TestCase):
    def test_career_with_levels(self):
        md = render({
            'slug': 'wick-trimmer', 'name': 'Wick Trimmer', 'source': 'TEST', 'chapter': 'ch1',
            'section': 'Wick Trimmer', 'page': 12, 'level': 2,
            'fields': {'class': 'Burghers', 'species': ['Human']},
            'content': [
                {'type': 'paragraph', 'text': 'Trimmers keep the harbour lamps burning.'},
                {'type': 'career_levels', 'levels': [
                    {'title': 'Lamp Boy', 'status': 'Brass 1', 'characteristics': ['Ag', 'Dex'],
                     'skills': ['Climb', 'Endurance'], 'talents': 'Night Vision, Sure-footed',
                     'trappings': ['Ladder']},
                    {'title': 'Trimmer', 'status': 'Brass 3', 'characteristics': ['WP'], 'skills': ['Perception']},
                ]},
            ]})
        self.assertTrue(md.startswith('---\nslug: wick-trimmer\nname: Wick Trimmer\nsource: TEST\n'
                                      'chapter: ch1\nsection: Wick Trimmer\npage: 12\n'))
        self.assertIn('class: Burghers\nspecies: ["Human"]\n---\n\n# Wick Trimmer\n', md)
        self.assertIn('| 1 | Lamp Boy | Brass 1 | Ag, Dex |', md)
        self.assertIn('***Lamp Boy*** (Brass 1)\n\n- **Skills:** Climb, Endurance\n'
                      '- **Talents:** Night Vision, Sure-footed\n- **Trappings:** Ladder', md)
        self.assertNotIn('**Talents:**', md.split('***Trimmer***')[1])

    def test_a_key_both_in_the_entry_and_its_fields_is_written_once(self):
        md = render({'slug': 'wick-care', 'name': 'Wick Care', 'source': 'TEST', 'chapter': 'ch1',
                     'section': 'Wick Care', 'page': 3, 'kind': 'procedure', 'fields': {'kind': 'procedure'},
                     'content': [{'type': 'paragraph', 'text': 'Trim the wick.'}]})
        self.assertEqual(md.count('\nkind: procedure\n'), 1)

    def test_creature_profile_named_like_the_entry_has_no_heading_of_its_own(self):
        md = render({'slug': 'fog-eel', 'name': 'Fog Eel', 'source': 'TEST', 'chapter': 'ch2', 'section': 'Fog Eel',
                     'content': [{'type': 'profile', 'name': 'Fog Eel',
                                  'characteristics': {'M': 6, 'WS': 35, 'BS': None, 'W': 9},
                                  'lines': [{'label': 'Traits', 'text': 'Bite +6, Night Vision'},
                                            {'label': 'Optional', 'text': 'Venom'}]}]})
        self.assertNotIn('## Fog Eel', md)
        self.assertIn('| M | WS | BS | W |\n|---|---|---|---|\n| 6 | 35 | — | 9 |', md)
        self.assertIn('**Traits:** Bite +6, Night Vision  \n**Optional:** Venom', md)

    def test_table_groups_and_sidebar(self):
        md = render({'slug': 'lamp-oils', 'name': 'Lamp Oils', 'source': 'TEST', 'chapter': 'ch1',
                     'section': 'Lamp Oils', 'content': [
                         {'type': 'table', 'title': 'Lamp Oils', 'columns': ['Roll', 'Oil'],
                          'rows': [['01–50', 'Whale'], ['51–00', 'Tallow']],
                          'groups': [{'before': 1, 'text': 'Cheap Oils'}]},
                         {'type': 'sidebar', 'title': 'Smoke', 'content': [{'type': 'paragraph', 'text': 'It rises.'}]}]})
        self.assertIn('| 01–50 | Whale |\n| ***Cheap Oils*** |  |\n| 51–00 | Tallow |', md)
        self.assertIn('> **Smoke**\n>\n> It rises.', md)

    def test_unknown_block_is_refused(self):
        with self.assertRaises(ValueError):
            render({'slug': 'x', 'name': 'X', 'content': [{'type': 'stat_block'}]})


if __name__ == '__main__':
    unittest.main()
