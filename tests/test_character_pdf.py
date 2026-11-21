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
                  'To do', 'Still to complete', 'Differs from the rules', 'xp-cost:',
                  'To settle', 'Her oath to the harbour', 'Satchel', '└ Boat Hook', 'Weapons', 'Damage', '1 gc', 'Mend the lamp',
                  'Age <b>31</b>', 'Eyes <b>Grey</b>', 'Not worked out', 'Fortune and Resolve', '<h2>Corruption</h2>'):
            self.assertIn(s, html, s)
        todo = html[html.index('class="todo"'):html.index('Basic skills')]
        self.assertLess(html.index('class="flow"'), html.index('class="todo"'))     # at the top of the columns, above the basic skills
        self.assertNotIn('background:', html)                                          # no fills: they waste ink
        for s in ('Still to complete', 'Differs from the rules', 'To settle', 'Not worked out'):
            self.assertIn(s, todo, s)
        m = bc.build(dict(r, to_complete=[{'id': 'xp-cost:*', 'what': 'Pay back the 87 XP'}]), Library(self.root, 'rock'))
        todo = character_pdf.document(m)
        todo = todo[todo.index('class="todo"'):todo.index('Basic skills')]
        self.assertLess(todo.index('Still to complete'), todo.index('Pay back the 87 XP'))
        self.assertNotIn('Differs from the rules', todo)
        for s in ('Accepted differences', 'the GM moved her on', 'House rules used', 'What rules add'):
            self.assertNotIn(s, html, s)
        self.assertEqual(html.count('class="page'), 3)
        self.assertEqual(html.count('class="page new'), 1)                 # only the play page forces a new page

    def test_spells_print_with_their_summary_and_bonuses_in_the_characters_numbers(self):
        p = os.path.join(self.root, 'library-data', 'spells', 'glow.json')
        import json
        with open(p) as f: e = json.load(f)
        e['fields']['summary'] = 'Lights a lamp Willpower Bonus + Toughness Bonus yards off on a Fellowship Test.'
        with open(p, 'w') as f: json.dump(e, f)
        r = record(spells=[{'ref': 'spells/glow', 'how': 'free'}, {'ref': 'spells/beam', 'how': 'free'}])
        m = bc.build(r, Library(self.root, 'rock'))
        self.assertEqual(m['spells'][0]['summary'], 'Lights a lamp 7 yards off on a Fellowship Test.')    # WPB 3 + TB 4
        self.assertTrue(any('Beam has no summary yet' in n for n in m['notes']))
        html = character_pdf.document(m)
        self.assertIn('Lights a lamp 7 yards off', html)
        self.assertIn('No summary yet', html)

    def test_talents_print_with_their_summary(self):
        import json
        p = os.path.join(self.root, 'library-data', 'talents', 'far-sight.json')
        with open(p) as f: e = json.load(f)
        e['fields']['summary'] = 'See Initiative Bonus miles further on a clear day.'
        with open(p, 'w') as f: json.dump(e, f)
        m = self.model()
        self.assertEqual([t['summary'] for t in m['talents']], ['See 3 miles further on a clear day.', None])
        self.assertTrue(any('Steady has no summary yet' in n for n in m['notes']))
        self.assertFalse(any('Far Sight has no summary' in n for n in m['notes']))
        html = character_pdf.document(m)
        self.assertIn('See 3 miles further on a clear day.', html)
        self.assertIn('1 of 4 · Tests: Watch at night · (LAMP p. 12)', html)
        self.assertEqual(character_pdf.short('(CRB, ch. 4 › Master Talent List, p. 132)'), '(CRB p. 132)')

    def test_the_play_page_marks_what_is_taken_and_lists_the_conditions(self):
        m = self.model(state={'wounds_taken': 2, 'fortune_spent': 1, 'corruption': 1, 'conditions': [{'name': 'Soaked', 'count': 2}]})
        html = character_pdf.document(m, [{'name': 'Soaked', 'cite': '(LAMP, p. 1)'}, {'name': 'Dazzled'}])
        play = html[html.index('class="page new play"'):]
        self.assertEqual(play.count('track on">✕'), 2 + 1 + 1 + 2)        # wounds, fortune, corruption, Soaked: marked, not filled
        self.assertIn('Dazzled', play)
        self.assertIn('Corruption', play)
        self.assertIn('+10 each', play)
        self.assertEqual(play[play.index('Advantage'):].count('class="track'), 10 + 12)   # a tally, then two conditions

    def test_a_house_rule_makes_advantage_one_box(self):
        import json
        p = os.path.join(self.root, 'campaigns', 'rock', 'campaign.json')
        with open(p) as f: c = json.load(f)
        c['house_rules'] = [{'id': 'edge', 'text': 'You have the edge (+10) or you do not', 'set': {'advantage': 'on-off'}}]
        with open(p, 'w') as f: json.dump(c, f)
        m = self.model()
        self.assertEqual(m['advantage'], {'style': 'on-off', 'cite': None, 'house_rule': 'You have the edge (+10) or you do not'})
        play = character_pdf.document(m)
        play = play[play.index('Advantage'):]
        self.assertIn('You have the edge (+10) or you do not', play)
        self.assertEqual(play.count('class="track'), 1)

    def test_text_from_the_record_is_escaped(self):
        html = character_pdf.document(self.model(name='<Mara & Co>'))
        self.assertIn('&lt;Mara &amp; Co&gt;', html)
        self.assertNotIn('<Mara', html)

    @unittest.skipUnless(character_pdf.find_browser(), 'no browser to print with')
    def test_the_pdf_flows_the_sheet_and_gives_the_play_page_its_own(self):
        import json
        p = os.path.join(self.root, 'mara.json')
        with open(p, 'w') as f: json.dump(record(), f)
        out = os.path.join(self.root, 'out')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'character_pdf.py'), p, '--library', self.root, '--campaign', 'rock',
                            '--out', out, '--pdf'], capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(out, 'mara.pdf'), 'rb') as f:
            self.assertEqual(len(re.findall(rb'/Type\s*/Page(?!s)', f.read())), 2)     # a short sheet, then the play page


if __name__ == '__main__':
    unittest.main()
