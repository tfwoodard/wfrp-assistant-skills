"""options.py (what a character can buy, priced) and apply.py (writing a purchase), on the invented
library of test_build_character.

Run: python3 -m unittest discover tests
"""
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
import options  # noqa: E402
from library import Library  # noqa: E402


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)
        self.path = os.path.join(self.root, 'mara.json')

    def tearDown(self):
        self.tmp.cleanup()

    def rules(self, *house_rules):
        p = os.path.join(self.root, 'campaigns', 'rock', 'campaign.json')
        with open(p) as f:
            c = json.load(f)
        c['house_rules'] = list(house_rules)
        with open(p, 'w') as f:
            json.dump(c, f)

    def write(self, rec):
        with open(self.path, 'w') as f:
            json.dump(rec, f)

    def apply(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, 'apply.py'), self.path, '--library', self.root,
                               '--campaign', 'rock', *args], capture_output=True, text=True)

    def saved(self):
        with open(self.path) as f:
            return json.load(f)


class Options(Case):
    def report(self, rec):
        return options.report(rec, Library(self.root, 'rock'))

    def test_a_level_one_character_sees_its_careers_wares_priced(self):
        o = self.report(record())
        self.assertEqual(o['xp'], {'total': 100, 'spent': 0, 'current': 100})
        self.assertEqual([(c['code'], c['advances'], c['next']) for c in o['characteristics']], [('I', 0, 20), ('T', 0, 20)])
        self.assertEqual([(s['name'], s['advances'], s['next'], s.get('choose', False)) for s in o['skills']],
                         [('Watch', 5, 12, False), ('Tending (Wicks)', 3, 8, False), ('Tending (Any)', 0, 8, True), ('Rowing', 0, 8, False)])
        self.assertEqual([(t['name'], t['times'], t['max'], t['next']) for t in o['talents']],
                         [('Steady', 1, 4, 200), ('Far Sight', 1, 2, 200)])

    def test_completing_the_level_counts_each_skill_once_and_gives_the_least_xp(self):
        c = self.report(record())['complete_level']
        self.assertEqual((c['level'], c['advances_each'], c['skills_done']), (1, 3, 2))       # Watch 5, Tending (Wicks) 3
        self.assertEqual(c['needs'], [{'what': 'Initiative: 3 more advances', 'xp': 60}, {'what': 'Toughness: 3 more advances', 'xp': 60},
                                      {'what': 'Rowing: 3 more advances', 'xp': 24}, {'what': 'Tending (Any): 3 more advances', 'xp': 24}])
        self.assertEqual(c['least_xp'], 168)

    def test_a_higher_level_sells_its_own_talents_and_counts_the_levels_below(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2}])
        o = self.report(r)
        self.assertEqual([t['name'] for t in o['talents']], ['Quick'])
        self.assertEqual([c['code'] for c in o['characteristics']], ['I', 'T', 'WP'])
        self.assertIn('Signals (Flag or Horn)', [s['name'] for s in o['skills']])
        self.assertEqual(o['complete_level']['advances_each'], 6)
        self.assertEqual([n['what'] for n in o['complete_level']['needs']][:3],
                         ['Initiative: 6 more advances', 'Toughness: 6 more advances', 'Willpower: 6 more advances'])
        self.assertEqual(o['unfinished'][0]['level'], 1)

    def test_house_rules_change_what_is_on_sale_and_its_price(self):
        self.rules({'id': 'flat', 'text': 'Flat talents', 'set': {'talent_cost': 'flat'}},
                   {'id': 'open', 'text': 'Earlier levels open', 'set': {'talents_from': 'levels-reached'}})
        r = record(careers=[{'ref': 'careers/warden', 'level': 2}])
        r['advances'] += [{'talent': 'talents/far-sight', 'how': 'free'}]
        o = self.report(r)
        t = {x['name']: x for x in o['talents']}
        self.assertEqual(sorted(t), ['Far Sight', 'Quick', 'Steady'])
        self.assertEqual((t['Steady']['next'], t['Quick']['next']), (100, 100))
        self.assertEqual((t['Far Sight']['at_max'], t['Far Sight']['next']), (True, None))
        self.assertIn('House rule: Flat talents', options.text(o))
        self.assertIn('Far Sight: 2 of 2; at its Max', options.text(o))


class Apply(Case):
    def test_a_purchase_is_priced_written_and_logged(self):
        self.write(record())
        r = self.apply('buy', '--skill', 'watch', '--count', '2', '--session', '4', '--date', '2026-01-02')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('watch x2: 24 XP', r.stdout)
        self.assertIn('XP to spend: 100 -> 76', r.stdout)
        self.assertIn('Watch 40 -> 42', r.stdout)
        rec = self.saved()
        self.assertEqual(rec['advances'][-1], {'skill': 'skills/watch', 'count': 2, 'how': 'xp', 'session': 4})
        self.assertNotIn('spent', rec['xp'])                               # worked out from the purchases
        self.assertEqual(rec['changelog'][-1], {'date': '2026-01-02', 'session': 4, 'text': 'Spent 24 XP on watch x2'})
        self.assertEqual(bc.build(rec, Library(self.root, 'rock'))['xp']['current'], 76)

    def test_a_characteristic_moves_everything_that_hangs_on_it(self):
        self.write(record(xp={'total': 500}))
        r = self.apply('buy', '--characteristic', 'toughness', '--count', '8')
        self.assertIn('Toughness x8: 205 XP', r.stdout)
        self.assertIn('Toughness 42 -> 50 (bonus 4 -> 5)', r.stdout)
        self.assertIn('Wounds 14 -> 16', r.stdout)
        self.assertIn('Corruption threshold 7 -> 8', r.stdout)

    def test_what_a_purchase_brings_with_it_is_said_and_it_is_still_written(self):
        self.write(record(xp={'total': 150}))
        r = self.apply('buy', '--talent', 'Far Sight')                     # the 2nd: 200 XP of 150
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Far Sight: 200 XP', r.stdout)
        self.assertIn('`xp-overspent`', r.stdout)
        self.assertIn('Far Sight carries no formula. Read it (LAMP, ch. 2 › Far Sight, p. 12)', r.stdout)
        self.assertEqual(self.saved()['advances'][-1], {'talent': 'talents/far-sight', 'how': 'xp'})
        r = self.apply('buy', '--talent', 'Far Sight', '--how', 'free', '--notes', 'A gift of the sea')
        self.assertIn('given in play, no XP', r.stdout)
        self.assertIn('`talent-max:far-sight`', r.stdout)
        self.assertEqual(self.saved()['advances'][-1]['notes'], 'A gift of the sea')

    def test_an_imported_record_keeps_its_spent_total_by_hand(self):
        rec = record(xp={'total': 100, 'spent': 40})
        rec['advances'] += [{'skill': 'skills/rowing', 'count': 4, 'how': 'imported'}]
        self.write(rec)
        r = self.apply('buy', '--skill', 'Rowing')
        self.assertIn('Rowing: 8 XP', r.stdout)
        self.assertIn('XP to spend: 60 -> 52', r.stdout)
        self.assertEqual(self.saved()['xp']['spent'], 48)

    def test_a_purchase_can_clear_a_difference_and_a_dry_run_writes_nothing(self):
        rec = record(careers=[{'ref': 'careers/warden', 'level': 2}], xp={'total': 1000})
        rec['advances'] += [{'characteristic': 'I', 'count': 3, 'how': 'xp'}, {'skill': 'skills/rowing', 'count': 3, 'how': 'xp'}]
        self.write(rec)
        r = self.apply('--dry-run', 'buy', '--characteristic', 'T', '--count', '3')
        self.assertIn("No longer differs: Warden level 1 (Lamp Boy) isn't complete", r.stdout)
        self.assertIn('nothing written', r.stdout)
        self.assertEqual(self.saved(), rec)

    def test_a_name_that_is_not_an_entry_is_refused_with_near_ones(self):
        self.write(record())
        r = self.apply('buy', '--talent', 'Stead')
        self.assertEqual(r.returncode, 1)
        self.assertIn("'Stead' isn't one entry among the talents in play: did you mean Steady?", r.stderr)
        self.assertEqual(self.apply('buy', '--characteristic', 'Luck').returncode, 1)
        self.assertEqual(self.saved(), record())

    def test_outside_the_career_costs_double_and_log_only_logs(self):
        self.write(record())
        r = self.apply('buy', '--skill', 'Tide Lore')
        self.assertIn('Tide Lore: 16 XP', r.stdout)
        self.assertIn("isn't in the career, so it costs double", r.stdout)
        r = self.apply('log', 'Lost the lamp overboard', '--date', '2026-01-03')
        self.assertEqual(self.saved()['changelog'][-1], {'date': '2026-01-03', 'text': 'Lost the lamp overboard'})


if __name__ == '__main__':
    unittest.main()
