"""The character builder (build_character.py), needs.py and the hand-kept sheet reader, on a small
invented library: its species, career, numbers and tables are made up for the test.

Run: python3 -m unittest discover tests
"""
import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'wfrp-character-sheet', 'scripts')
sys.path.insert(0, SCRIPTS)
import build_character as bc  # noqa: E402
import needs  # noqa: E402
import read_sheet_export as rse  # noqa: E402
from library import Library  # noqa: E402


def para(text):
    return {'type': 'paragraph', 'text': text}


def head(text, level=2):
    return {'type': 'heading', 'level': level, 'text': text}


def table(title, columns, rows):
    return {'type': 'table', 'title': title, 'columns': columns, 'rows': rows}


def write(root, cat, entries, base='library-data'):
    d = os.path.join(root, base, cat)
    os.makedirs(d, exist_ok=True)
    idx = []
    for e in entries:
        e = dict({'source': 'LAMP', 'chapter': 'ch2', 'section': e['name'], 'page': 12, 'content': []}, **e)
        with open(os.path.join(d, e['slug'] + '.json'), 'w') as f:
            json.dump(e, f)
        idx.append(dict({k: v for k, v in e.items() if k not in ('content', 'fields')}, **e.get('fields', {})))
    with open(os.path.join(d, '_index.json'), 'w') as f:
        json.dump(idx, f)


def library(root, house_rules=()):
    write(root, 'species', [{'slug': 'keepers', 'name': 'Keepers', 'aliases': ['Keeper'], 'fields': {
        'characteristics': {c: '2d10+23' for c in bc.CHARS}, 'wounds': 'SB+(2 × TB)+WPB', 'fate': 1,
        'resilience': 1, 'extra_points': 2, 'movement': 4,
        'skills': ['Watch', 'Tending (Wicks)', 'Rowing'],
        'talents': ['Far Sight', {'choose_one': ['Steady', 'Quick']}]}}])
    write(root, 'careers', [{'slug': 'warden', 'name': 'Warden', 'fields': {
        'class': 'Watchers', 'species': ['Keeper'], 'levels': ['Lamp Boy', 'Warden', 'Head Warden'],
        'status': ['Brass 2', 'Silver 1', 'Silver 4'], 'earning_skill': 'Watch',
        'advances': {
            '1': {'status': 'Brass 2', 'characteristics': ['I', 'T'], 'skills': ['Watch', 'Tending (Any)', 'Rowing'],
                  'talents': ['Steady', 'Far Sight'], 'trappings': ['Lamp']},
            '2': {'status': 'Silver 1', 'characteristics': ['WP'], 'skills': ['Signals (Flag or Horn)'],
                  'talents': ['Quick'], 'trappings': []},
            '3': {'status': 'Silver 4', 'characteristics': ['Fel'], 'skills': [], 'talents': [], 'trappings': []}}}},
        {'slug': 'ferryman', 'name': 'Ferryman', 'fields': {
            'class': 'Rivermen', 'species': ['Marsh Folk'], 'levels': ['Poler'], 'status': ['Brass 1'],
            'advances': {'1': {'characteristics': ['S'], 'skills': ['Rowing'], 'talents': []}}}}])
    write(root, 'skills', [
        {'slug': 'watch', 'name': 'Watch', 'fields': {'characteristic': 'I', 'advanced': False, 'grouped': False}},
        {'slug': 'rowing', 'name': 'Rowing', 'fields': {'characteristic': 'S', 'advanced': False, 'grouped': False}},
        {'slug': 'tending', 'name': 'Tending', 'fields': {'characteristic': 'Dex', 'advanced': False, 'grouped': True}},
        {'slug': 'signals', 'name': 'Signals', 'fields': {'characteristic': 'Int', 'advanced': True, 'grouped': True}},
        {'slug': 'tide-lore', 'name': 'Tide Lore', 'fields': {'characteristic': 'Int', 'advanced': True, 'grouped': False}},
        {'slug': 'humming', 'name': 'Humming', 'fields': {}}])
    write(root, 'talents', [
        {'slug': 'steady', 'name': 'Steady', 'fields': {'max': 'Toughness Bonus', 'tests': 'Watch at night'}},
        {'slug': 'quick', 'name': 'Quick', 'fields': {'max': '1', 'effects': [{'on': 'WP', 'add': 5, 'at': 0}]}},
        {'slug': 'hum', 'name': 'Hum', 'fields': {'max': '1'}},
        {'slug': 'far-sight', 'name': 'Far Sight', 'fields': {'max': '2'}},
        {'slug': 'lamp-magic', 'name': 'Arcane Magic', 'fields': {'max': '1'}, 'content': [
            table('Arcane Magic Spell Costs', ['Spells known', 'A new spell'], [['Up to Intelligence Bonus × 1', '80 XP'], ['Up to Intelligence Bonus × 2', '160 XP']])]},
        {'slug': 'bright-blood', 'name': 'Bright Blood', 'fields': {'effects': [
            {'on': 'spell_cost', 'multiply': 0.5, 'at': 0, 'applies': {'specialisation': 'Quick Study'}}]}, 'content': [para('Two gifts.')]},
        {'slug': 'glow-magic', 'name': 'Petty Magic', 'fields': {'max': '1'}, 'content': [
            table('Petty Magic Spell Costs', ['Spells known', 'A new spell'], [['Up to Willpower Bonus × 1', '30 XP'], ['Up to Willpower Bonus × 2', '60 XP']])]},
        {'slug': 'odd', 'name': 'Odd', 'fields': {'max': 'Number of lamps lit', 'effects': [{'on': 'luck', 'add': 1, 'at': 0}]}}])
    write(root, 'spells', [
        {'slug': 'glow', 'name': 'Glow', 'fields': {'kind': 'petty', 'lore': None, 'cn': 0, 'range': 'Willpower yards',
                                                     'target': 'AoE (Willpower Bonus yards)', 'duration': 'Initiative Bonus Rounds'}},
        {'slug': 'beam', 'name': 'Beam', 'fields': {'kind': 'lore', 'lore': 'Lamps', 'cn': 4, 'range': 'Touch',
                                                     'target': '1', 'duration': 'Instant'}}] +
        [{'slug': n, 'name': n.title(), 'fields': {'kind': 'petty', 'cn': 0}} for n in ('glint', 'gleam', 'glare', 'glimmer', 'gloss', 'glitter', 'glisten')] +
        [{'slug': 'ray', 'name': 'Ray', 'fields': {'kind': 'lore', 'lore': 'Lamps', 'cn': 5}},
         {'slug': 'spark', 'name': 'Spark', 'fields': {'kind': 'arcane', 'cn': 2}},
         {'slug': 'tide-rite', 'name': 'Tide Rite', 'fields': {'kind': 'ritual', 'cn': 9}}])
    write(root, 'trappings', [
        {'slug': 'boat-hook', 'name': 'Boat Hook', 'fields': {'kind': 'melee', 'group': 'Basic', 'enc': '1',
                                                             'reach': 'Long', 'damage': '+SB+1', 'qualities': ['Hooked']}},
        {'slug': 'boat-hook-pier', 'name': 'Boat Hook', 'source': 'PIER', 'relations': [{'role': 'version-of', 'to': 'trappings/boat-hook'}],
         'fields': {'kind': 'melee', 'group': 'Basic', 'enc': '2', 'reach': 'Long', 'damage': '+SB+3', 'qualities': []}},
        {'slug': 'oilskin', 'name': 'Oilskin', 'fields': {'kind': 'armour', 'enc': '1', 'locations': 'Arms, Body', 'armour_points': '1'}},
        {'slug': 'cap', 'name': 'Cap', 'fields': {'kind': 'armour', 'enc': '1', 'locations': 'Head', 'armour_points': '1'}},
        {'slug': 'satchel', 'name': 'Satchel', 'fields': {'kind': 'container', 'enc': '1', 'carries': '2'}},
        {'slug': 'lamp', 'name': 'Lamp', 'fields': {'kind': 'tool', 'enc': '1'}},
        {'slug': 'anchor', 'name': 'Anchor', 'fields': {'kind': 'item', 'enc': '6'}}])
    write(root, 'tables', [{'slug': 'sea-madness', 'name': 'Sea Madness', 'content': [
        table('Sea Madness', ['d10', 'Madness', 'What it does'],
              [['1–5', 'Salt Dreams', 'Stubborn and cold'], ['6–9', 'Gull Fear', 'Afraid of gulls'], ['10', 'Gull Fear', 'Twice over']])],
        'fields': {'rows': {'Salt Dreams': {'effects': [{'on': 'WP', 'add': 10}, {'on': 'Fel', 'add': -10}]}}}},
        {'slug': 'lucky-gifts', 'name': 'Lucky Gifts', 'content': [
            table('Lucky Gifts', ['d10', 'Gift'], [['1–5', 'Quick'], ['6–10', 'Steady']])]}])
    write(root, 'rules', [
        {'slug': 'step-1-species', 'name': 'Choose a Folk', 'content': [para('Roll for a folk and keep it for a bonus.')],
         'fields': {'effects': [{'on': 'xp', 'add': 15, 'at': 0, 'applies': {'how': ['rolled']}}]}},
        {'slug': 'step-2-class-and-career', 'name': 'Choose a Calling', 'content': [para('Keep the first roll, or one of three.')],
         'fields': {'effects': [{'on': 'xp', 'add': 40, 'at': 0, 'applies': {'how': ['rolled']}},
                                {'on': 'xp', 'add': 20, 'at': 0, 'applies': {'how': ['one-of-three']}}]}},
        {'slug': 'characteristics', 'name': 'Numbers', 'content': [para('Keep the dice, or move them about.')]},
        {'slug': 'species-skills-and-talents', 'name': 'What a Folk Teaches', 'content': [para('One well, one a little.')]},
        {'slug': 'career-skills-and-talents', 'name': 'What a Calling Teaches', 'content': [para('Share out ten.')]},
        {'slug': 'advance-characteristics', 'name': 'Calling Numbers', 'content': [para('Share out three.')]},
        {'slug': 'keepers-of-the-isles', 'name': 'Keepers of the Isles', 'content': [
            {'type': 'heading', 'level': 2, 'text': 'North Isle'}, para('**Skills**: Rowing, Watch **Talents**: Quick, Far Sight')]},
        {'slug': 'advancing-through-your-career', 'name': 'Advancing', 'content': [
            table('Characteristic and Skill Improvement XP Costs', ['Advances', 'Characteristics', 'Skills'],
                  [['0 to 5', '20', '8'], ['6 to 10', '35', '12']]),
            head('Non-career Advances'), para('Twice the price.'), head('Talent Advances'), para('A hundred, then more.')]},
        {'slug': 'changing-career', 'name': 'Changing', 'content': [
            head('Completing a Career'), table('Level Advances', ['Level', 'Advances'], [['1', '3'], ['2', '6']])]},
        {'slug': 'movement-attribute', 'name': 'Moving', 'content': [
            table('Movement', ['Movement', 'Walk', 'Run'], [['3', '6', '12'], ['4', '8', '16']])]},
        {'slug': 'homelands', 'name': 'Homelands', 'content': [
            head('North Rock'), para('A cold place.'),
            para('**Skills**: Watch, Tide Lore, Signals (Horn) **Talents**: Far Sight, Steady *or* Odd'),
            head('South Rock'), para('A warm place.')]},
        {'slug': 'steady-at-sea', 'name': 'Steady at Sea', 'relations': [{'role': 'adds-to', 'to': 'talents/steady'}], 'fields': {'effects': [
            {'on': 'wounds', 'add': 'TB * times', 'at': 0, 'applies': {'career': ['careers/ferryman']}},
            {'on': 'fate', 'add': 1, 'at': 0, 'applies': {'class': 'Rivermen', 'guild': ['Polers']}}]}},
        {'slug': 'encumbrance', 'name': 'Carrying'}, {'slug': 'corrupting', 'name': 'Rot'},
        {'slug': 'step-3-attributes', 'name': 'Attributes'}])
    with open(os.path.join(root, 'library.json'), 'w') as f:
        json.dump({'edition': '4e', 'sources': [{'code': 'LAMP', 'chapters': []}, {'code': 'PIER', 'chapters': []}]}, f)
    c = os.path.join(root, 'campaigns', 'rock')
    os.makedirs(c)
    with open(os.path.join(c, 'campaign.json'), 'w') as f:
        json.dump({'slug': 'rock', 'sources': ['PIER', 'LAMP'], 'house_rules': list(house_rules)}, f)


def record(**over):
    r = {
        'schema': 2, 'slug': 'mara', 'name': 'Mara',
        'species': {'ref': 'species/keepers', 'how': 'chosen'},
        'careers': [{'ref': 'careers/warden', 'level': 1, 'how': 'chosen'}],
        'characteristics': {'initial': {'WS': 30, 'BS': 30, 'S': 31, 'T': 42, 'I': 35, 'Ag': 30, 'Dex': 28,
                                        'Int': 33, 'WP': 39, 'Fel': 25}},
        'extra_points': {'fate': 1, 'resilience': 1},
        'advances': [
            {'skill': 'skills/watch', 'count': 5, 'how': 'species'},
            {'skill': 'skills/tending', 'specialisation': 'Wicks', 'count': 3, 'how': 'species'},
            {'talent': 'talents/far-sight', 'how': 'species'},
            {'talent': 'talents/steady', 'how': 'species'}],
        'spells': [], 'trappings': [], 'xp': {'total': 100},
        'state': {'wounds_taken': 2, 'fortune_spent': 1, 'corruption': 1}}
    r.update(copy.deepcopy(over))
    return r


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        library(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, rec, campaign='rock'):
        return bc.build(rec, Library(self.root, campaign))

    def ids(self, m):
        return [d['id'] for d in m['differences']]


class Numbers(Case):
    def test_attributes_come_from_the_species_and_the_tables(self):
        m = self.build(record())
        self.assertEqual(m['characteristics']['T'], {'initial': 42, 'advances': 0, 'current': 42, 'bonus': 4})
        self.assertEqual(m['wounds'], {'max': 3 + 2 * 4 + 3, 'formula': 'SB+(2 × TB)+WPB', 'taken': 2})
        self.assertEqual(m['movement'], {'base': 4, 'walk': 8, 'run': 16})
        self.assertEqual(m['fate'], {'fate': 2, 'fortune': 1})
        self.assertEqual(m['resilience']['resilience'], 2)
        self.assertEqual(m['corruption']['threshold'], 4 + 3)
        self.assertEqual(m['encumbrance']['max'], 3 + 4)
        self.assertEqual(m['career']['status'], 'Brass 2')
        self.assertEqual(m['career']['level_name'], 'Lamp Boy')
        self.assertEqual(m['differences'], [])

    def test_effects_change_numbers_and_say_where_from(self):
        m = self.build(record(effects=[{'on': 'wounds', 'add': 'TB * times', 'from': 'talents/steady'},
                                       {'on': 'WP', 'add': 5, 'from': 'talents/quick'},
                                       {'on': 'movement', 'add': -1, 'from': 'a limp'}]))
        self.assertEqual(m['characteristics']['WP']['initial'], 44)
        self.assertEqual(m['characteristics']['WP']['rolled'], 39)
        self.assertEqual(m['wounds']['max'], 3 + 8 + 4 + 4)
        self.assertEqual(m['movement'], {'base': 3, 'walk': 6, 'run': 12})

    def test_a_number_the_table_lacks_is_said_not_guessed(self):
        m = self.build(record(effects=[{'on': 'movement', 'add': 3, 'from': 'wings'}]))
        self.assertIsNone(m['movement']['walk'])
        self.assertTrue(any('no row for Movement 7' in n for n in m['notes']))

    def test_starting_values_outside_the_species_roll_are_reported_not_changed(self):
        r = record()
        r['characteristics']['initial']['WP'] = 65
        m = self.build(r)
        self.assertEqual(m['characteristics']['WP']['current'], 65)
        self.assertIn('initial:WP', self.ids(m))
        self.assertIn('25 to 43', m['differences'][0]['text'])

    def test_extra_points_must_add_up(self):
        m = self.build(record(extra_points={'fate': 3, 'resilience': 0}))
        self.assertIn('extra-points', self.ids(m))


class EffectsOnEntries(Case):
    def quick(self, **over):
        r = record(**over)
        r['advances'] += [{'talent': 'talents/quick', 'how': 'free'}]
        return r

    def test_an_effect_written_on_a_talent_is_applied_without_the_record_saying_so(self):
        m = self.build(self.quick())
        self.assertEqual(m['characteristics']['WP'], {'initial': 44, 'advances': 0, 'current': 44, 'bonus': 4, 'rolled': 39,
                                                     'effects': [{'on': 'WP', 'add': 5, 'from': 'talents/quick', 'at': 0}]})
        self.assertEqual(m['effects'], [{'on': 'WP', 'add': 5, 'from': 'talents/quick', 'at': 0}])
        self.assertEqual(m['wounds']['max'], 3 + 8 + 4)                # the bonus it raised counts everywhere
        self.assertIn('- Willpower +5: `talents/quick`', bc.markdown(m))
        self.assertEqual(self.build(record())['effects'], [])          # not taken, not applied

    def test_a_record_line_repeating_the_entrys_effect_is_not_counted_twice(self):
        m = self.build(self.quick(effects=[{'on': 'WP', 'add': 5, 'from': 'talents/quick'}]))
        self.assertEqual(m['characteristics']['WP']['initial'], 44)
        self.assertTrue(any('repeats the one on that entry' in n for n in m['notes']))

    def test_an_effect_on_an_entry_that_adds_to_a_talent_applies_to_whom_it_says(self):
        r = record(careers=[{'ref': 'careers/ferryman', 'level': 1}])
        r['advances'] += [{'talent': 'talents/steady', 'how': 'free'}]         # Steady twice
        m = self.build(r)
        self.assertEqual(m['wounds']['max'], 3 + 8 + 3 + 4 * 2)
        self.assertIn({'on': 'wounds', 'add': 8, 'from': 'rules/steady-at-sea', 'at': 0}, m['effects'])
        self.assertEqual(self.build(record())['wounds']['max'], 3 + 8 + 3)     # a Warden: it isn't about them

    def test_what_the_build_does_not_know_is_said_and_left_out(self):
        r = record(careers=[{'ref': 'careers/ferryman', 'level': 1}])
        r['advances'] += [{'talent': 'talents/odd', 'how': 'free'}]
        m = self.build(r)
        self.assertEqual(m['fate']['fate'], 2)
        self.assertTrue(any("applies by 'guild'" in n for n in m['notes']))
        self.assertTrue(any("an effect on 'luck'" in n for n in m['notes']))


class TableRows(Case):
    def test_a_row_the_record_names_brings_its_effects_and_is_shown_with_what_it_says(self):
        m = self.build(record(psychology=['Duty', {'table': 'tables/sea-madness', 'row': 'salt dreams', 'from': 'talents/steady'}]))
        self.assertEqual((m['characteristics']['WP']['initial'], m['characteristics']['Fel']['initial']), (49, 15))
        self.assertEqual(m['effects'], [{'on': 'WP', 'add': 10, 'from': 'tables/sea-madness#Salt Dreams'},
                                        {'on': 'Fel', 'add': -10, 'from': 'tables/sea-madness#Salt Dreams'}])
        self.assertEqual(m['psychology'], ['Duty', {'name': 'Salt Dreams', 'table': 'tables/sea-madness', 'cells': ['Stubborn and cold'],
                                                    'why': 'talents/steady', 'cite': '(LAMP, ch. 2 › Sea Madness, p. 12)'}])
        md = bc.markdown(m)
        self.assertIn('- Duty', md)
        self.assertIn('- Salt Dreams (Stubborn and cold), from `talents/steady` (LAMP, ch. 2 › Sea Madness, p. 12)', md)
        self.assertIn('- Fellowship -10: `tables/sea-madness#Salt Dreams`', md)

    def test_a_row_without_a_formula_says_so_and_a_row_that_is_not_one_row_is_reported(self):
        m = self.build(record(mutations=[{'table': 'tables/sea-madness', 'row': 'Twice over'}]))
        self.assertEqual(m['mutations'][0]['name'], 'Twice over')
        self.assertTrue(any('Twice over (Sea Madness): the row carries no formula' in n for n in m['notes']))
        for row, n in (('Gull Fear', 2), ('Mermaid Sight', 0)):
            m = self.build(record(mutations=[{'table': 'tables/sea-madness', 'row': row}]))
            d = next(x for x in m['differences'] if x['id'].startswith('row:sea-madness/'))
            self.assertIn(f'names {n} rows', d['text'])
            self.assertNotIn('mutations', m)


class SkillsAndTalents(Case):
    def test_every_basic_skill_is_listed_and_advanced_ones_only_when_taken(self):
        m = self.build(record())
        self.assertEqual([r['name'] for r in m['skills']['basic']], ['Rowing', 'Tending', 'Tending (Wicks)', 'Watch'])
        watch = m['skills']['basic'][-1]
        self.assertEqual((watch['advances'], watch['total'], watch['career']), (5, 40, True))
        self.assertFalse(m['skills']['basic'][1]['career'])      # the bare grouped line is no one specialisation
        self.assertTrue(m['skills']['basic'][2]['career'])       # "Tending (Any)"
        self.assertEqual(m['skills']['advanced'], [])

    def test_a_list_of_alternatives_covers_each_of_them_only(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2, 'left_incomplete': [1]}])
        r['advances'] += [{'skill': 'skills/signals', 'specialisation': 'Horn', 'count': 1, 'how': 'xp'},
                          {'skill': 'skills/signals', 'specialisation': 'Smoke', 'count': 1, 'how': 'xp'}]
        m = self.build(r)
        adv = {s['name']: s for s in m['skills']['advanced']}
        self.assertTrue(adv['Signals (Horn)']['career'])
        self.assertFalse(adv['Signals (Smoke)']['career'])
        self.assertEqual([p['xp'] for p in m['xp']['purchases']], [8, 16])     # outside the career: double
        self.assertTrue(any('costs double' in n for n in m['notes']))

    def test_a_single_choice_is_one_specialisation_recorded_or_else_worked_out_and_said(self):
        def sig(**career):
            r = record(careers=[dict({'ref': 'careers/warden', 'level': 2, 'left_incomplete': [1]}, **career)], xp={'total': 500})
            r['advances'] += [{'skill': 'skills/signals', 'specialisation': 'Flag', 'count': 2, 'how': 'xp'},
                              {'skill': 'skills/signals', 'specialisation': 'Horn', 'count': 1, 'how': 'xp'}]
            m = self.build(r)
            return m, {x['name']: x['career'] for x in m['skills']['advanced']}, [p['xp'] for p in m['xp']['purchases']]
        m, career, paid = sig()                                   # nothing recorded: the more advanced one
        self.assertEqual(career, {'Signals (Flag)': True, 'Signals (Horn)': False})
        self.assertEqual(paid, [16, 16])                          # Horn is outside the career: double
        self.assertTrue(any('Signals (Flag or Horn) = Signals (Flag)' in n and '`choices`' in n for n in m['notes']))
        m, career, paid = sig(choices={'Signals (Flag or Horn)': 'horn'})
        self.assertEqual(career, {'Signals (Flag)': False, 'Signals (Horn)': True})
        self.assertEqual(paid, [32, 8])
        self.assertFalse(any('Taken as the career' in n for n in m['notes']))
        m, career, paid = sig(choices={'Signals (Flag or Horn)': 'Smoke'})
        self.assertIn('career-choice:signals-flag-or-horn', self.ids(m))
        self.assertEqual(career, {'Signals (Flag)': False, 'Signals (Horn)': False})

    def test_a_career_skill_the_career_settles_is_shown_without_advances(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2, 'left_incomplete': [1], 'choices': {'Signals (Flag or Horn)': 'Horn'}}])
        m = self.build(r)
        self.assertEqual([(x['name'], x['advances'], x['career']) for x in m['skills']['advanced']], [('Signals (Horn)', 0, True)])
        r['advances'] += [{'skill': 'skills/signals', 'specialisation': 'horn', 'count': 1, 'how': 'xp'}]
        self.assertEqual([x['advances'] for x in self.build(r)['skills']['advanced'] if x['name'].startswith('Signals')], [1])
        r = record(careers=[{'ref': 'careers/warden', 'level': 2, 'left_incomplete': [1]}])          # nothing chosen: nothing shown
        self.assertEqual(self.build(r)['skills']['advanced'], [])

    def test_an_open_name_covers_every_specialisation_and_an_exact_one_is_not_a_choice(self):
        r = record()
        r['advances'] += [{'skill': 'skills/tending', 'specialisation': 'Nets', 'count': 1, 'how': 'xp'}]
        m = self.build(r)
        self.assertEqual({x['name']: x['career'] for x in m['skills']['basic'] if x['name'].startswith('Tending (')},
                         {'Tending (Nets)': True, 'Tending (Wicks)': True})          # "Tending (Any)"
        self.assertFalse(any('Taken as the career' in n for n in m['notes']))

    def test_a_grouped_skill_needs_its_specialisation_and_an_unmarked_one_is_said(self):
        r = record()
        r['advances'] += [{'skill': 'skills/signals', 'count': 1, 'how': 'free'},
                          {'skill': 'skills/humming', 'count': 1, 'how': 'free'}]
        m = self.build(r)
        self.assertIn('skill-specialisation:signals', self.ids(m))
        self.assertTrue(any('Humming' in n and 'basic or advanced' in n for n in m['notes']))
        self.assertTrue(any('Humming' in n and 'no characteristic' in n for n in m['notes']))

    def test_talent_maximums_are_worked_out_and_checked(self):
        r = record()
        r['advances'] += [{'talent': 'talents/far-sight', 'times': 2, 'how': 'xp'}]
        m = self.build(r)
        t = {x['name']: x for x in m['talents']}
        self.assertEqual((t['Steady']['max'], t['Steady']['tests']), (4, 'Watch at night'))
        self.assertEqual((t['Far Sight']['times'], t['Far Sight']['max']), (3, 2))
        self.assertIn('talent-max:far-sight', self.ids(m))

    def test_rules_that_add_to_a_talent_are_pointed_at_not_applied(self):
        m = self.build(record())
        t = {x['name']: x for x in m['talents']}
        self.assertEqual(t['Steady']['added_by'], ['rules/steady-at-sea'])
        self.assertNotIn('added_by', t['Far Sight'])
        self.assertIn('- Steady: `rules/steady-at-sea`', bc.markdown(m))

    def test_a_maximum_that_is_not_a_sum_is_said(self):
        r = record()
        r['advances'] += [{'talent': 'talents/odd', 'how': 'free'}]
        m = self.build(r)
        self.assertTrue(any("'Number of lamps lit'" in n for n in m['notes']))

    def test_a_talent_from_nowhere_is_reported_unless_freely_given(self):
        r = record()
        r['advances'] += [{'talent': 'talents/lamp-magic', 'specialisation': 'Lamps', 'how': 'imported'}]
        self.assertIn('talent-source:lamp-magic/lamps', self.ids(self.build(r)))
        r['advances'][-1]['how'] = 'free'
        self.assertNotIn('talent-source:lamp-magic/lamps', self.ids(self.build(r)))

    def test_both_of_a_species_choice_is_reported_unless_a_career_gives_one(self):
        r = record(species={'ref': 'species/keepers', 'origin': 'rules/homelands#North Rock'})
        r['advances'] = [{'talent': 'talents/steady', 'how': 'imported'}, {'talent': 'talents/odd', 'how': 'imported'}]
        self.assertNotIn('species-choice:steady+odd', self.ids(self.build(r)))     # Steady is a Warden talent
        r['careers'] = [{'ref': 'careers/ferryman', 'level': 1}]
        m = self.build(r)
        self.assertIn('species-choice:steady+odd', self.ids(m))
        self.assertIn('career-species:careers/ferryman', self.ids(m))

    def test_an_origin_gives_its_own_lists(self):
        r = record(species={'ref': 'species/keepers', 'origin': 'rules/homelands#North Rock'})
        r['advances'] = [{'talent': 'talents/quick', 'how': 'imported'}]
        m = self.build(r)
        self.assertEqual(m['species']['origin'], 'North Rock')
        self.assertIn('talent-source:quick', self.ids(m))            # the species' own choice no longer applies
        r['species']['origin'] = 'rules/homelands#South Rock'
        m = self.build(r)
        self.assertTrue(any('no Skills and Talents lists' in n for n in m['notes']))
        self.assertNotIn('talent-source:quick', self.ids(m))


class Experience(Case):
    def test_costs_follow_the_table_and_the_number_already_taken(self):
        r = record(xp={'total': 400, 'spent': 20 * 5 + 35 + 8 * 0 + 12 * 2 + 100 + 200})
        r['advances'] += [{'characteristic': 'T', 'count': 6, 'how': 'xp'},
                          {'skill': 'skills/watch', 'count': 2, 'how': 'xp'},          # the 6th and 7th
                          {'talent': 'talents/steady', 'how': 'xp'},                   # the 2nd time
                          {'talent': 'talents/far-sight', 'how': 'free'}]
        m = self.build(r)
        self.assertEqual([p['by_the_rules'] for p in m['xp']['purchases']], [135, 24, 200])
        self.assertEqual(m['xp']['worked_out'], 359)
        self.assertIn('xp-spent', self.ids(m))               # the record's sum was wrong
        self.assertEqual(m['characteristics']['T']['current'], 48)

    def test_a_recorded_price_that_differs_and_overspending_are_reported(self):
        r = record(xp={'total': 10})
        r['advances'] += [{'skill': 'skills/rowing', 'count': 1, 'how': 'xp', 'xp': 5}]
        m = self.build(r)
        self.assertIn('xp-cost:4', self.ids(m))
        self.assertEqual(m['xp']['spent'], 5)
        r['xp'] = {'total': 3}
        self.assertIn('xp-overspent', self.ids(self.build(r)))

    def test_imported_advances_have_no_history_and_say_so(self):
        r = record(xp={'total': 50, 'spent': 45})
        r['advances'] += [{'skill': 'skills/rowing', 'count': 4, 'how': 'imported'}]
        m = self.build(r)
        self.assertIsNone(m['xp']['worked_out'])
        self.assertEqual(m['xp']['current'], 5)
        self.assertTrue(any('imported' in n for n in m['notes']))

    def test_the_table_running_out_is_said(self):
        r = record()
        r['advances'] += [{'characteristic': 'I', 'count': 11, 'how': 'xp'}]
        m = self.build(r)
        self.assertTrue(any("doesn't go as far as 11" in n for n in m['notes']))
        self.assertIsNone(m['xp']['worked_out'])

    def test_a_level_left_behind_must_be_complete_or_marked(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2}])
        m = self.build(r)
        d = next(x for x in m['differences'] if x['id'] == 'level-complete:warden/1')
        self.assertIn('I, T below 3 advances', d['text'])
        self.assertIn('2 of its skills', d['text'])
        r['advances'] += [{'characteristic': 'I', 'count': 3, 'how': 'xp'}, {'characteristic': 'T', 'count': 3, 'how': 'xp'},
                          {'skill': 'skills/rowing', 'count': 3, 'how': 'xp'}]
        self.assertNotIn('level-complete:warden/1', self.ids(self.build(r)))
        r = record(careers=[{'ref': 'careers/warden', 'level': 3, 'left_incomplete': [1]}])
        m = self.build(r)
        self.assertNotIn('level-complete:warden/1', self.ids(m))
        self.assertIn('level-complete:warden/2', self.ids(m))


class CreationXP(Case):
    def test_each_step_gives_what_its_rule_says_for_how_it_was_settled(self):
        r = record(species={'ref': 'species/keepers', 'how': 'rolled'},
                   careers=[{'ref': 'careers/warden', 'level': 1, 'how': 'one-of-three'}],
                   characteristics=dict(record()['characteristics'], how='rearranged'))
        c = self.build(r)['xp']['at_creation']
        self.assertEqual([(x['step'], x['how'], x['xp']) for x in c['steps']],
                         [('species', 'rolled', 15), ('career', 'one-of-three', 20), ('characteristics', 'rearranged', None)])
        self.assertIsNone(c['xp'])                                      # Numbers has no formula yet
        m = self.build(r)
        self.assertTrue(any('Numbers has no formula for the XP it gives' in n for n in m['notes']))
        rules = os.path.join(self.root, 'library-data', 'rules', 'characteristics.json')
        with open(rules) as f: e = json.load(f)
        e['fields'] = {'effects': [{'on': 'xp', 'add': 30, 'at': 0, 'applies': {'how': ['rearranged']}}]}
        with open(rules, 'w') as f: json.dump(e, f)
        m = self.build(r)
        self.assertEqual(m['xp']['at_creation']['xp'], 65)
        self.assertIn('Of the total, from creation: 65 (species rolled: 15 XP', bc.markdown(m))
        r['xp'] = {'total': 100, 'bonus_at_creation': 60}
        self.assertEqual(self.ids(self.build(r)), ['xp-creation'])
        r['species']['how'] = 'guessed'
        self.assertIn('creation-how:species', self.ids(self.build(r)))

    def test_a_campaign_can_turn_the_bonus_off(self):
        p = os.path.join(self.root, 'campaigns', 'rock', 'campaign.json')
        with open(p) as f: c = json.load(f)
        c['creation'] = {'starting_xp_bonus': False}
        with open(p, 'w') as f: json.dump(c, f)
        m = self.build(record(species={'ref': 'species/keepers', 'how': 'rolled'}, characteristics=dict(record()['characteristics'], how='rearranged')))
        self.assertEqual(m['xp']['at_creation']['xp'], 0)
        self.assertTrue(any('starting_xp_bonus is false' in n for n in m['notes']))

    def test_a_step_not_said_is_not_worked_out_and_says_so(self):
        m = self.build(record(species={'ref': 'species/keepers', 'how': 'imported'}))
        self.assertIsNone(m['xp']['at_creation']['xp'])
        self.assertEqual(m['xp']['at_creation']['steps'][1]['xp'], 0)  # a chosen calling gives nothing
        self.assertTrue(any("doesn't say how the species was settled" in n for n in m['notes']))


class CreationGrants(Case):
    GRANTS = {
        'species-skills-and-talents': [
            {'id': 'skills', 'how': 'species', 'kind': 'skill', 'from': 'species', 'picks': [{'count': 1, 'advances': 5}, {'count': 1, 'advances': 3}], 'at': 0},
            {'id': 'talents', 'how': 'species', 'kind': 'talent', 'from': 'species', 'at': 0},
            {'id': 'lucky', 'how': 'species', 'kind': 'talent', 'from': 'table', 'table': 'tables/lucky-gifts', 'count': 'species-random', 'at': 0}],
        'career-skills-and-talents': [
            {'id': 'skills', 'how': 'career', 'kind': 'skill', 'from': 'first-career-level', 'total': 10, 'most': 6, 'at': 0},
            {'id': 'talent', 'how': 'career', 'kind': 'talent', 'from': 'first-career-level', 'count': 1, 'at': 0}],
        'advance-characteristics': [
            {'id': 'numbers', 'how': 'career', 'kind': 'characteristic', 'from': 'first-career-level', 'total': 3, 'at': 0}]}

    def grant(self, **only):
        for slug, gs in self.GRANTS.items():
            if only and slug not in only: continue
            p = os.path.join(self.root, 'library-data', 'rules', slug + '.json')
            with open(p) as f: e = json.load(f)
            e['fields'] = {'grants': gs}
            with open(p, 'w') as f: json.dump(e, f)

    def made(self, *extra):
        r = record()
        r['advances'] += [{'skill': 'skills/rowing', 'count': 6, 'how': 'career'}, {'skill': 'skills/tending', 'specialisation': 'Nets', 'count': 4, 'how': 'career'},
                          {'characteristic': 'I', 'count': 2, 'how': 'career'}, {'characteristic': 'T', 'count': 1, 'how': 'career'}] + list(extra)
        return r

    def test_without_grants_creation_is_not_checked_and_says_so(self):
        m = self.build(self.made())
        self.assertEqual(m['creation'], [])
        self.assertTrue(any('carry no grants yet' in n for n in m['notes']))

    def test_what_creation_gave_is_checked_against_the_grants(self):
        self.grant()
        m = self.build(self.made())
        self.assertEqual(self.ids(m), [])
        self.assertEqual([(c['id'], c['given'], c['left']) for c in m['creation']],
                         [('skills', {5: 1, 3: 1}, {}), ('talents', 2, None), ('lucky', 0, 0), ('skills', 10, 0), ('talent', 0, 1), ('numbers', 3, 0)])

    def test_too_much_or_from_the_wrong_list_is_a_difference(self):
        self.grant()
        m = self.build(self.made({'skill': 'skills/signals', 'specialisation': 'Flag', 'count': 1, 'how': 'species'},
                                 {'characteristic': 'WP', 'count': 1, 'how': 'career'},
                                 {'talent': 'talents/steady', 'how': 'career'}, {'talent': 'talents/far-sight', 'how': 'career'}))
        self.assertEqual(self.ids(m), ['creation:species-skills-and-talents/skills:signals-flag',      # not counted in what is given
                                       'creation:career-skills-and-talents/talent', 'creation:advance-characteristics/numbers:wp'])
        r = self.made()
        r['advances'][-4]['count'] = 7                       # more than 6 in one skill, 11 in all
        self.assertIn('at most 6 in one', ' '.join(d['text'] for d in self.build(r)['differences']))

    def test_random_talents_come_from_their_table_as_many_as_the_species_lists(self):
        self.grant()
        sp = os.path.join(self.root, 'library-data', 'species', 'keepers.json')
        with open(sp) as f: e = json.load(f)
        e['fields']['talents'] = ['Far Sight', {'choose_one': ['Steady', 'Quick']}, {'random': 1}]
        with open(sp, 'w') as f: json.dump(e, f)
        r = self.made({'talent': 'talents/quick', 'how': 'species'}, {'talent': 'talents/hum', 'how': 'species'})
        self.assertEqual(self.ids(self.build(r)), ['creation:species-skills-and-talents/talents:hum'])     # not on the list or the table
        r = self.made({'talent': 'talents/quick', 'how': 'species'})            # Steady from the list, Quick rolled
        m = self.build(r)
        self.assertEqual(self.ids(m), [])
        c = {g['id']: g for g in m['creation'] if g['how'] == 'species' and g['kind'] == 'talent'}
        self.assertEqual((c['talents']['taken'], c['talents']['to_take'], c['lucky']['taken'], c['lucky']['left']),
                         (['Far Sight', 'Steady'], [], ['Quick'], 0))
        r['advances'].append({'talent': 'talents/steady', 'how': 'species', 'times': 1})
        self.assertIn('creation:species-skills-and-talents/lucky', self.ids(self.build(r)))   # two rolled, one given
        r = self.made()
        r['advances'] = [a for a in r['advances'] if a.get('talent') != 'talents/steady']
        c = {g['id']: g for g in self.build(r)['creation'] if g['kind'] == 'talent' and g['how'] == 'species'}
        self.assertEqual((c['talents']['to_take'], c['lucky']['left']), (['Steady or Quick'], 1))

    def test_a_line_no_grant_covers_is_a_difference(self):
        self.grant(**{'species-skills-and-talents': 1})
        self.assertIn('creation:career-skill', self.ids(self.build(self.made())))


class SpellsAndTrappings(Case):
    def test_spell_numbers_use_the_casters_own(self):
        r = record(spells=[{'ref': 'spells/glow', 'how': 'free'}, {'ref': 'spells/beam', 'how': 'free'}])
        r['advances'] += [{'talent': 'talents/glow-magic', 'how': 'free'},
                          {'talent': 'talents/lamp-magic', 'specialisation': 'Lamps', 'how': 'free'}]
        m = self.build(r)
        self.assertEqual((m['spells'][0]['range'], m['spells'][0]['target'], m['spells'][0]['duration']),
                         ('39 yards', 'AoE (3 yards)', '3 Rounds'))
        self.assertEqual(m['differences'], [])

    def caster(self, spells, **over):
        r = record(spells=spells, xp={'total': 2000}, **over)
        r['advances'] += [{'talent': 'talents/glow-magic', 'how': 'free'},
                          {'talent': 'talents/lamp-magic', 'specialisation': 'Lamps', 'how': 'free'}]
        return r

    def test_spells_are_priced_from_the_talents_tables_by_how_many_are_known(self):
        petty = ['glow', 'glint', 'gleam', 'glare', 'glimmer', 'gloss', 'glitter', 'glisten']
        spells = [{'ref': f'spells/{n}', 'how': 'talent' if i < 3 else 'xp'} for i, n in enumerate(petty)]      # Willpower Bonus 3
        spells += [{'ref': 'spells/beam', 'how': 'xp'}, {'ref': 'spells/spark', 'how': 'xp'}, {'ref': 'spells/ray', 'how': 'free'},
                   {'ref': 'spells/ray', 'how': 'xp'}]
        m = self.build(self.caster(spells))
        self.assertEqual([(p['spell'], p['xp']) for p in m['xp']['purchases']],
                         [('Glare', 30), ('Glimmer', 60), ('Gloss', 60), ('Glitter', 60), ('Glisten', 90),   # 3 known, 4-6, then "and so on"
                          ('Beam', 80), ('Spark', 80), ('Ray', 80)])                                         # the lore's own count: 0, 1, 3
        self.assertEqual(m['xp']['worked_out'], 540)
        self.assertEqual(m['differences'], [])

    def test_an_effect_can_multiply_the_price_of_spells_for_one_specialisation(self):
        spells = [{'ref': 'spells/glow', 'how': 'xp'}, {'ref': 'spells/beam', 'how': 'xp'}]
        r = self.caster(spells)
        r['advances'] += [{'talent': 'talents/bright-blood', 'specialisation': 'Quick Study', 'how': 'free'}]
        m = self.build(r)
        self.assertEqual([p['xp'] for p in m['xp']['purchases']], [15, 40])
        self.assertTrue(all(isinstance(p['xp'], int) for p in m['xp']['purchases']))
        self.assertIn({'on': 'spell_cost', 'multiply': 0.5, 'from': 'talents/bright-blood', 'at': 0}, m['effects'])
        self.assertIn('- Spell cost × 0.5: `talents/bright-blood`', bc.markdown(m))
        r['advances'][-1]['specialisation'] = 'Strong Arm'
        self.assertEqual([p['xp'] for p in self.build(r)['xp']['purchases']], [30, 80])

    def test_what_cannot_be_priced_is_said(self):
        m = self.build(self.caster([{'ref': 'spells/glow', 'how': 'imported'}, {'ref': 'spells/tide-rite', 'how': 'xp'},
                                    {'ref': 'spells/glint'}, {'ref': 'spells/beam', 'how': 'talent'}]))
        self.assertIsNone(m['xp']['worked_out'])
        self.assertTrue(any('imported from a sheet' in n for n in m['notes']))
        self.assertTrue(any('Tide Rite is a ritual: the build has no price' in n for n in m['notes']))
        self.assertEqual(self.ids(m), ['spell-how:glint', 'spell-free:beam'])
        four = [{'ref': f'spells/{n}', 'how': 'talent'} for n in ('glow', 'glint', 'gleam', 'glare')]
        self.assertEqual(self.ids(self.build(self.caster(four))), ['petty-free'])

    def test_spells_without_their_talent_are_reported(self):
        m = self.build(record(spells=[{'ref': 'spells/glow', 'how': 'free'}, {'ref': 'spells/beam', 'how': 'free'}]))
        self.assertEqual(self.ids(m), ['spell-talent:glow', 'spell-lore:beam'])

    def test_trappings_weapons_armour_and_what_counts(self):
        r = record(trappings=[
            {'ref': 'trappings/boat-hook'},
            {'ref': 'trappings/oilskin', 'worn': True}, {'ref': 'trappings/cap'},
            {'id': 'bag', 'ref': 'trappings/satchel'},
            {'ref': 'trappings/lamp', 'qty': 2, 'in': 'bag'},
            {'id': 'tin', 'name': 'Tin of wicks', 'enc': 1, 'in': 'bag'},
            {'name': 'Spare wick', 'in': 'tin'},
            {'ref': 'trappings/anchor', 'stowed': True},
            {'name': 'Lost thing', 'in': 'nowhere'}])
        m = self.build(r)
        hook = m['trappings'][0]
        self.assertEqual(hook['ref'], 'trappings/boat-hook-pier')            # PIER comes first in the campaign's sources
        self.assertEqual(hook['weapon'], {'group': 'Basic', 'qualities': [], 'reach': 'Long', 'damage': 6, 'damage_text': '+SB+3'})
        self.assertEqual([t['depth'] for t in m['trappings']], [0, 0, 0, 0, 1, 1, 2, 0, 0])
        self.assertEqual([t['counts'] for t in m['trappings']], [2, 0, 1, 1, 0, 0, 0, 0, 0])
        self.assertEqual(m['encumbrance']['carried'], 4)
        self.assertEqual(m['armour'], {'Head': 0, 'Left Arm': 1, 'Right Arm': 1, 'Body': 1, 'Left Leg': 0, 'Right Leg': 0})
        self.assertEqual(self.ids(m), ['trapping-in:nowhere'])

    def test_a_ref_that_is_not_in_the_library_is_reported(self):
        m = self.build(record(trappings=[{'ref': 'trappings/sextant'}]))
        self.assertEqual(self.ids(m), ['missing:trappings/sextant'])


class Settling(Case):
    def test_exceptions_and_house_rules_move_a_difference_to_accepted(self):
        r = record(exceptions=[{'id': 'initial:WP', 'why': 'Rolled before the table changed'},
                               {'id': 'initial:Fel', 'why': 'Not needed'}], xp={'total': 1000})
        r['characteristics']['initial']['WP'] = 65
        r['advances'] += [{'talent': 'talents/far-sight', 'times': 2, 'how': 'xp'}]
        m = self.build(r)
        self.assertEqual(self.ids(m), ['talent-max:far-sight'])
        self.assertEqual([(a['id'], a['why']) for a in m['accepted']], [('initial:WP', 'Rolled before the table changed')])
        self.assertTrue(any("'initial:Fel' matches no difference" in n for n in m['notes']))
        with open(os.path.join(self.root, 'campaigns', 'rock', 'campaign.json')) as f:
            c = json.load(f)
        c['house_rules'] = ['Lamps burn twice as long', {'id': 'sharp-eyes', 'text': 'Far Sight has no limit', 'accepts': ['talent-max:far-sight*']}]
        with open(os.path.join(self.root, 'campaigns', 'rock', 'campaign.json'), 'w') as f:
            json.dump(c, f)
        m = self.build(r)
        self.assertEqual(m['differences'], [])
        self.assertEqual(m['accepted'][-1]['house_rule'], 'sharp-eyes')


class HouseRules(Case):
    def rules(self, *house_rules):
        path = os.path.join(self.root, 'campaigns', 'rock', 'campaign.json')
        with open(path) as f:
            c = json.load(f)
        c['house_rules'] = list(house_rules)
        with open(path, 'w') as f:
            json.dump(c, f)

    def bought(self):
        r = record(careers=[{'ref': 'careers/warden', 'level': 2}], xp={'total': 1000})
        r['advances'] += [{'talent': 'talents/steady', 'how': 'xp'},          # the 2nd time; a level 1 talent
                          {'talent': 'talents/steady', 'how': 'xp'}]          # the 3rd
        return r

    def test_by_the_books_talents_cost_more_each_time_and_come_from_the_current_level(self):
        m = self.build(self.bought())
        self.assertEqual([p['xp'] for p in m['xp']['purchases']], [200, 300])
        self.assertTrue(any("isn't a talent of the current career level" in n for n in m['notes']))
        self.assertEqual(m['house_rules'], {})

    def test_a_house_rule_sets_flat_talent_costs_and_opens_earlier_levels(self):
        self.rules({'id': 'flat-talents', 'text': 'A talent costs the same every time', 'set': {'talent_cost': 'flat'}},
                   {'id': 'old-lessons', 'text': 'Earlier levels still teach', 'set': {'talents_from': 'levels-reached'}})
        m = self.build(self.bought())
        self.assertEqual([p['xp'] for p in m['xp']['purchases']], [100, 100])
        self.assertFalse(any("isn't a talent of" in n for n in m['notes']))
        self.assertEqual(m['house_rules']['talent_cost'], {'value': 'flat', 'house_rule': 'flat-talents', 'text': 'A talent costs the same every time'})
        self.assertIn('House rule: Earlier levels still teach (talents from: levels-reached)', bc.markdown(m))

    def test_a_setting_the_build_does_not_know_is_said_and_not_applied(self):
        self.rules({'id': 'cheap', 'text': 'Half price', 'set': {'talent_cost': 'half', 'skill_cost': 'flat'}})
        m = self.build(self.bought())
        self.assertEqual([p['xp'] for p in m['xp']['purchases']], [200, 300])
        self.assertEqual(sum("which the build doesn't know" in n for n in m['notes']), 2)

    def test_an_unfinished_level_stays_on_the_sheet_when_a_house_rule_accepts_it(self):
        self.rules({'id': 'by-plot', 'text': 'The GM moves careers on by the story', 'accepts': ['level-complete:*']})
        m = self.build(record(careers=[{'ref': 'careers/warden', 'level': 2}]))
        self.assertEqual(m['differences'], [])
        self.assertEqual(m['accepted'][0]['house_rule'], 'by-plot')
        self.assertEqual(m['career']['to_complete'], [{'career': 'Warden', 'level': 1, 'level_name': 'Lamp Boy',
                                                       'missing': ['I, T below 3 advances', '2 of its skills at 3 advances (8 needed)']}])
        self.assertIn('Still to complete in Warden 1 (Lamp Boy): I, T below 3 advances; 2 of its skills at 3 advances (8 needed)', bc.markdown(m))
        self.assertEqual(self.build(record())['career']['to_complete'], [])


class Sheet(Case):
    def test_the_readable_sheet_has_every_part(self):
        r = record(trappings=[{'ref': 'trappings/boat-hook'}], spells=[{'ref': 'spells/glow', 'how': 'free'}], incomplete=['Pick a name for the boat'],
                   money={'gc': 0, 'ss': 3, 'd': 4}, ambitions={'short': 'Mend the lamp', 'long': ''})
        md = bc.markdown(self.build(r))
        for part in ('# Mara', 'Keepers · Watchers · Warden 1: Lamp Boy · Status Brass 2', '## To settle', 'Pick a name for the boat',
                     '## Differs from the rules', '`spell-talent:glow`', '| Watch | ✓ | I | 5 | 40 |', '| Steady | 1 | 4 | Watch at night |',
                     '| Glow | petty | 0 | 39 yards |', 'Damage 6 (+SB+3)', 'Money: 0 gc, 3 ss, 4 d', '- short: Mend the lamp'):
            self.assertIn(part, md)

    def test_needs_lists_what_a_build_would_read(self):
        os.remove(os.path.join(self.root, 'library-data', 'talents', 'steady.json'))
        os.remove(os.path.join(self.root, 'library-data', 'rules', 'movement-attribute.json'))
        n = needs.needs(record(), self.root, 'rock')
        self.assertEqual(sorted(n['missing']), ['library-data/rules/movement-attribute.json', 'library-data/talents/steady.json'])
        self.assertIn('library-data/species/keepers.json', n['read'])


EXPORT = '''## Sheet name: Description and Talents
Category,Field,,Data
Basics,Name,,Mara
,Species,,Keeper (North Rock)
,Class,,Watcher
,Career,,Warden
,Career Level,,Lamp Boy
,Status,,Brass 2
,Age,,31
Ambitions,Short-term,,Mend the lamp
,Long-term,,"See the far shore, once"
Party,Name
,Long-term,,Keep the light
Psychology,Motivation,,Duty
,Afraid of gulls
Corruption,Points,,1
,Mutations

Talent,Count,Max,Test,Description
Steady,1,4,Watch at night,"Words the sheet's keeper copied, which stay behind."
Far Sight,1,2

## Sheet name: Crunch
Characteristics,,,,,,,,,,,,Fate,Fortune,,Movement,,,Experience,,,Wealth
,WS,BS,S,T,I,Ag,Dex,Int,WP,Fel,,2,OO,,Base,4,,Current,-5,,D,4
Initial,30,30,31,42,35,30,28,33,39,25,,,,,Walk,8,,Spent,105,,SS,3
Advances,0,0,0,0,0,0,0,0,0,0,,Resilience,Resolve,,Run,16,,Total,100,,GC,0
Current,30,30,31,42,35,30,28,33,39,25,,2,O
Bonus,3,3,3,4,3,3,2,3,3,2,,,,,Wounds,Taken
,,,,,,,,,,,,Encumbrance,,,14,OOO
,Head,LA,RA,Body,LL,RL,Shield,,,,,Total,2
Armor,0,1,1,1,0,0,0,,,,,Max,7,,Corruption,7

Basic Skill Name,,,,,,Cur,Characteristic,,Adv,Skill,,Advanced Skill Name,,,,,,Cur,Characteristic,,Adv,Skill
Rowing,,,,,,Y,S,31,0,31,,Signals (Horn) - Loud,,,,,,,Int,33,2,35
Watch,,,,,,Y,I,35,4,39,,,,,,,,,,,0,0

## Sheet name: Trappings
Name,Enc,Qualities,Locations,AP,Group,Range/Reach,Damage
Boat Hook,1,Hooked,,0,Basic,Long,4
Satchel,1,,,0
- Tin of wicks,1,,,0
- - Spare wick,0,,,0

## Sheet name: Spells
Name,Lore,CN,Range,Target,Duration,Damage,Description
Glow,Petty,0,39 yds,AoE (3 yds),3 rounds,,"More copied words, also left behind."

## Sheet name: Doodles
Gull,Gull
'''


class KeptSheet(Case):
    def test_the_export_is_read_tab_by_tab_and_book_text_is_left_behind(self):
        s = rse.read(EXPORT)
        self.assertEqual((s['name'], s['species'], s['origin'], s['career_level'], s['status']),
                         ('Mara', 'Keeper', 'North Rock', 'Lamp Boy', 'Brass 2'))
        self.assertEqual(s['ambitions'], {'short': 'Mend the lamp', 'long': 'See the far shore, once'})
        self.assertEqual(s['psychology'], ['Motivation: Duty', 'Afraid of gulls'])
        self.assertEqual(s['talents'], [{'name': 'Steady', 'count': 1, 'max': 4, 'tests': 'Watch at night'},
                                        {'name': 'Far Sight', 'count': 1, 'max': 2, 'tests': None}])
        self.assertEqual(s['characteristics']['T'], {'initial': 42, 'advances': 0, 'current': 42, 'bonus': 4})
        self.assertEqual((s['fate'], s['resilience'], s['wounds']), (2, 2, 14))
        self.assertEqual(s['movement'], {'base': 4, 'walk': 8, 'run': 16})
        self.assertEqual(s['xp'], {'current': -5, 'spent': 105, 'total': 100})
        self.assertEqual(s['wealth'], {'d': 4, 'ss': 3, 'gc': 0})
        self.assertEqual(s['encumbrance'], {'total': 2, 'max': 7})
        self.assertEqual(s['armour']['la'], 1)
        self.assertEqual(s['skills'][-1], {'name': 'Signals (Horn)', 'advanced': True, 'career': False,
                                           'characteristic': 'Int', 'advances': 2, 'total': 35})
        self.assertEqual([(t['name'], t['depth']) for t in s['trappings']],
                         [('Boat Hook', 0), ('Satchel', 0), ('Tin of wicks', 1), ('Spare wick', 2)])
        self.assertEqual(s['spells'], [{'name': 'Glow', 'lore': 'Petty', 'cn': 0, 'range': '39 yds',
                                        'target': 'AoE (3 yds)', 'duration': '3 rounds'}])
        self.assertEqual(s['tabs_not_read'], ['Doodles'])
        self.assertNotIn('copied', json.dumps(s))

    def test_the_build_is_compared_with_what_the_sheet_shows(self):
        r = record(spells=[{'ref': 'spells/glow', 'how': 'free'}], xp={'total': 100, 'spent': 105})
        r['advances'] += [{'skill': 'skills/signals', 'specialisation': 'Horn', 'count': 2, 'how': 'imported'}]
        got = {d['what']: (d['shown'], d['built']) for d in bc.compare(self.build(r), rse.read(EXPORT))}
        self.assertEqual(got, {
            'Watch advances': (4, 5), 'Watch total': (39, 40),
            'Skill Tending': ('not on the sheet', 28), 'Skill Tending (Wicks)': ('not on the sheet', 31),
            'Encumbrance carried': (2, 0)})


if __name__ == '__main__':
    unittest.main()
