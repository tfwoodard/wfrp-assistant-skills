"""detectors.py: fields an entry's own text states, proposed from invented text."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'skills', 'wfrp-import', 'scripts'))
import detectors  # noqa: E402


def fields(props):
    return {p['field']: p['value'] for p in props}


class Stacks(unittest.TestCase):
    def test_a_condition_that_says_it_doesnt_stack(self):
        for text in ('Unlike most, Soaked does not stack.', 'This Condition does not stack.', "It doesn't stack: you are wet or not."):
            self.assertEqual(fields(detectors.propose('rules', 'condition', 'Soaked', {}, text)), {'stacks': False}, text)

    def test_look_alikes_propose_nothing(self):
        for text in ('The bonus does not increase with more Soaked Conditions.',     # not "stack"
                     'Toppled does not stack, but Soaked does.'):                    # about another condition
            self.assertEqual(detectors.propose('rules', 'condition', 'Soaked', {}, text), [], text)
        self.assertEqual(detectors.propose('rules', 'procedure', 'Soaking', {}, 'It does not stack.'), [])   # not a condition

    def test_the_plan_already_saying_so_or_otherwise(self):
        self.assertEqual(detectors.propose('rules', 'condition', 'Soaked', {'stacks': False}, 'Soaked does not stack.'), [])
        p = detectors.propose('rules', 'condition', 'Soaked', {'stacks': True}, 'Soaked does not stack.')
        self.assertEqual((p[0]['value'], p[0]['plan']), (False, True))                 # listed for the Librarian


class Skills(unittest.TestCase):
    def test_a_lead_line(self):
        self.assertEqual(fields(detectors.propose('skills', None, 'Rowing', {}, '(S), Advanced Rowing moves a boat.')),
                         {'characteristic': 'S', 'advanced': True, 'grouped': False})
        self.assertEqual(fields(detectors.propose('skills', None, 'Tending', {}, '(Dex), Basic, Grouped Tending keeps lamps.')),
                         {'characteristic': 'Dex', 'advanced': False, 'grouped': True})
        self.assertEqual(fields(detectors.propose('skills', None, 'Wick Lore', {}, '(Int), Advanced, Specialisation A lore.')),
                         {'characteristic': 'Int', 'advanced': True, 'grouped': False})   # Specialisation isn't Grouped

    def test_a_sentence_naming_the_characteristic(self):
        got = detectors.propose('skills', None, 'Gull Sense', {}, 'Gull Sense is an Advanced Skill. It is based on Initiative.')
        self.assertEqual(fields(got), {'advanced': True, 'grouped': False, 'characteristic': 'I'})
        self.assertIn('based on Initiative', got[0]['says'])

    def test_a_specialisation_takes_its_base_skills(self):
        base = {'name': 'Signals', 'slug': 'signals', 'characteristic': 'Int', 'advanced': True}
        got = detectors.propose('skills', None, 'Signals (Lamp)', {}, 'Flashing a lamp across the bay.', base)
        self.assertEqual(fields(got), {'characteristic': 'Int', 'advanced': True, 'grouped': False})
        self.assertIn('specialisation of Signals', got[0]['says'])
        self.assertEqual(detectors.propose('skills', None, 'Signals', {}, 'Flashing a lamp.', base), [])   # no brackets
        self.assertEqual(detectors.base_name('Lore (Runes)'), 'Lore')

    def test_the_lead_line_says_first(self):
        base = {'name': 'Signals', 'characteristic': 'Int', 'advanced': True}
        got = detectors.propose('skills', None, 'Signals (Horn)', {}, '(Fel), Advanced A horn call.', base)
        self.assertEqual([(p['field'], p['value'], p['detector']) for p in got if p['field'] == 'characteristic'],
                         [('characteristic', 'Fel', 'skill-lead'), ('characteristic', 'Int', 'specialisation')])  # both, to look at

    def test_plain_text_reads_nested_blocks_without_marks(self):
        blocks = [{'type': 'paragraph', 'text': '**(S)**, Advanced'}, {'type': 'sidebar', 'content': [{'type': 'paragraph', 'text': '*It* does not stack.'}]}]
        self.assertEqual(detectors.plain_text(blocks), '(S), Advanced\nIt does not stack.')


if __name__ == '__main__':
    unittest.main()


class AddsTo(unittest.TestCase):
    def setUp(self):
        import json, tempfile
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, 'careers'))
        with open(os.path.join(self.tmp.name, 'careers', '_index.json'), 'w') as f:
            json.dump([{'slug': 'lamplighter', 'name': 'Lamplighter'}, {'slug': 'warden', 'name': 'Warden'}], f)

    def tearDown(self):
        self.tmp.cleanup()

    def propose(self, entries, out, relations=None):
        import convert_rules
        report = {}
        convert_rules.propose_adds_to(entries, out, {'source': 'LAMP', 'chapter': 'ch4', 'relations': relations or {}},
                                      self.tmp.name, report)
        return [(r['entry'], r['to']) for r in report.get('proposed_relations', [])], report

    def test_a_box_entry_adds_to_the_entry_it_is_printed_in(self):
        entries = [{'spec': {'name': 'Gull Rock'}}, {'spec': {'name': 'A Seed of Trouble'}, 'host': 'Gull Rock', 'from_box': '4.1'}]
        out = [('lore', {'name': 'Gull Rock', 'slug': 'gull-rock'}), ('lore', {'name': 'A Seed of Trouble', 'slug': 'a-seed-of-trouble'})]
        got, report = self.propose(entries, out)
        self.assertEqual(got, [('lore/a-seed-of-trouble', 'lore/gull-rock')])
        self.assertIn('printed in a box within Gull Rock', report['proposed_relations'][0]['says'])
        self.assertIn('--relation adds-to:lore/gull-rock --plan sources/LAMP/plans/ch4.json', report['proposed_relations'][0]['set_with'])
        got, _ = self.propose(entries, out, {'lore/a-seed-of-trouble': [{'role': 'adds-to', 'to': 'lore/elsewhere'}]})
        self.assertEqual(got, [])                                                  # the plan says already

    def test_a_rule_named_after_a_career(self):
        out = [('rules', {'name': 'Dwarf Lamplighter', 'slug': 'dwarf-lamplighter'}),
               ('rules', {'name': 'Lamplighters Guild', 'slug': 'lamplighters-guild'})]       # not "ends in"
        got, _ = self.propose([], out)
        self.assertEqual(got, [('rules/dwarf-lamplighter', 'careers/lamplighter')])
