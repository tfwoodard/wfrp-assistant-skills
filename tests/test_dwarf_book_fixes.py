"""Tests for what a book of one people needed: tables transcribed by hand and checked against
the page, single career levels offered in place of another career's, boxes that go with the
heading they follow, item descriptions under headings, marks on item names. Invented lines only.

Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts'))

import convert_rules  # noqa: E402
import items  # noqa: E402


def ln(text, page=1, bold=False, heading=None, box=None, column='left', top=None, spans=None):
    spans = spans or [(text, bold)]
    ln.y = getattr(ln, 'y', 100) + 12
    return {'text': ' '.join(t for t, _ in spans), 'page': page, 'column': column, 'heading': heading, 'box': box,
            'bold': all(b for _, b in spans), 'italic': False, 'size': 10.0, 'x0': 50.0, 'x1': 280.0,
            'top': float(top if top is not None else ln.y), 'baseline': float(ln.y),
            'words': [[w, 50.0 + 8 * k, 55.0 + 8 * k] for k, w in enumerate(' '.join(t for t, _ in spans).split())],
            'spans': [{'text': t, 'bold': b, 'italic': False, 'size': 10.0} for t, b in spans]}


def para(text):
    return {'type': 'paragraph', 'text': text}


def head(text, level=3):
    return {'type': 'heading', 'level': level, 'text': text}


class HandTableTest(unittest.TestCase):
    def lines(self):
        return [ln('Keepers are chosen by lot.'), ln('KEEPER LOT TABLE', heading=5), ln('Pier Rock'), ln('Duty Lamp Lamp'),
                ln('1'), ln('Trimmer 01-50 01-'), ln('Tower'), ln('Warden 51-100 30'), ln('31-100'),
                ln('1 Only on feast days.'), ln('Duty Lamp Lamp'), ln('The lot is drawn at dusk.')]

    def plan(self, **kw):
        return [dict({'page': 1, 'starts': 'KEEPER LOT TABLE', 'ends_before': 'The lot is drawn', 'title': 'Keeper Lot Table',
                      'columns': ['Duty', 'Notes', 'Pier Lamp', 'Rock Lamp'],
                      'rows': [['Trimmer', '1', '01-50', '01-30'], ['Warden', '', '51-100', '31-100']],
                      'groups': [{'before': 1, 'text': 'Tower'}], 'footnotes': ['1 Only on feast days.'],
                      'added': ['Notes'], 'also': ['KEEPER LOT TABLE', 'Duty Lamp Lamp']}, **kw)]

    def test_a_transcript_that_matches_the_page_replaces_its_lines(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out, entries = convert_rules.hand_tables(self.lines(), self.plan(), report)
        self.assertEqual(report['errors'], [])
        self.assertEqual([l['text'][:20] for l in out], ['Keepers are chosen b', out[1]['text'][:20], 'The lot is drawn at '])
        block = out[1]['block']
        self.assertEqual((block['rows'][0], block['groups'], block['footnotes']),
                         (['Trimmer', '1', '01-50', '01-30'], [{'before': 1, 'text': 'Tower'}], ['1 Only on feast days.']))
        self.assertIsNone(out[1]['heading'])
        self.assertEqual(entries, [])
        self.assertEqual(report['hand_tables'][0]['checked'], 'letter for letter')
        self.assertEqual(report['left_out'], ['KEEPER LOT TABLE', 'Duty Lamp Lamp'])

    def test_a_transcript_that_differs_is_an_error_naming_the_words(self):
        plan = self.plan()
        plan[0]['rows'][1][3] = '31-99'
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out, _ = convert_rules.hand_tables(self.lines(), plan, report)
        self.assertEqual(len(out), len(self.lines()))                 # nothing replaced
        self.assertIn('the transcript and the page differ', report['errors'][0]['error'])
        # The words on one side only (a cell the page wraps shows on both sides: a hint, not the check).
        self.assertIn('31-100', report['errors'][0]['only_on_the_page'])
        self.assertIn('31-99', report['errors'][0]['only_in_the_transcript'])

    def test_with_a_slug_it_is_an_entry_too_and_may_be_that_alone(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out, entries = convert_rules.hand_tables(self.lines(), self.plan(slug='keeper-lots', in_text=False), report)
        self.assertEqual([l['text'] for l in out], ['Keepers are chosen by lot.', 'The lot is drawn at dusk.'])
        self.assertEqual(entries[0][0]['slug'], 'keeper-lots')
        self.assertEqual(len(entries[0][1]['rows']), 2)

    def test_a_missing_start_line_or_a_short_row_is_an_error(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        convert_rules.hand_tables(self.lines(), self.plan(starts='LOT TABLE'), report)
        plan = self.plan()
        plan[0]['rows'][0].pop()
        convert_rules.hand_tables(self.lines(), plan, report)
        self.assertIn("no line 'LOT TABLE'", report['errors'][0]['error'])
        self.assertIn('a row with other than 4 cells', report['errors'][1]['error'])


class LevelUpdatesTest(unittest.TestCase):
    def lines(self, sentence=True, trappings=True):
        out = [ln('Lamp Keepers of the Rock', heading=4), ln('Rock keepers work alone.'), ln('Storm Warden', heading=6),
               ln('They watch the weather.')]
        if sentence:
            out += [ln('Storm Wardens replace the 2nd level of the Keeper (Tower Book) or'),
                    ln('Trimmer (Pier Book page 9) Career. They replace their Career level’s'),
                    ln('corresponding Characteristic with Initiative.')]
        out += [ln('Storm Warden — Silver 2', bold=True),
                ln('Skills: Climb, Lore (Weather),', spans=[('Skills:', True), ('Climb, Lore (Weather),', False)]),
                ln('Perception'),
                ln('Talents: Night Vision', spans=[('Talents:', True), ('Night Vision', False)])]
        if trappings:
            out += [ln('Trappings: Storm Glass', spans=[('Trappings:', True), ('Storm Glass', False)])]
        return out + [ln('Fog Caller', heading=6), ln('Fog callers ring the bell.')]

    def test_a_level_is_a_block_numbered_by_the_sentence_above_it(self):
        report = {'errors': [], 'left_out': [], 'questions': []}
        out, found = convert_rules.level_updates(self.lines(), report, 'Rock Keepers')
        self.assertEqual(report['errors'], [])
        self.assertEqual(found, [{'title': 'Storm Warden', 'status': 'Silver 2', 'level': 2,
                                  'replaces': [{'career': 'Keeper', 'source': 'Tower Book'},
                                               {'career': 'Trimmer', 'source': 'Pier Book page 9'}],
                                  'characteristic': 'Initiative', 'skills': ['Climb', 'Lore (Weather)', 'Perception'],
                                  'talents': ['Night Vision'], 'trappings': ['Storm Glass']}])
        block = next(l['block'] for l in out if l.get('block'))
        self.assertEqual((block['type'], block['first_level'], block['levels'][0]['title']), ('career_levels', 2, 'Storm Warden'))
        self.assertEqual(out[-2]['text'], 'Fog Caller')
        self.assertEqual(report['left_out'], ['Skills:', 'Talents:', 'Trappings:'])

    def test_a_level_with_no_trappings_is_asked_about(self):
        report = {'errors': [], 'left_out': [], 'questions': []}
        _, found = convert_rules.level_updates(self.lines(trappings=False), report, 'Rock Keepers')
        self.assertEqual(report['errors'], [])
        self.assertNotIn('trappings', found[0])
        self.assertEqual(report['questions'][0]['kind'], 'level-without-trappings')

    def test_a_level_with_no_sentence_is_an_error(self):
        report = {'errors': [], 'left_out': [], 'questions': []}
        convert_rules.level_updates(self.lines(sentence=False), report, 'Rock Keepers')
        self.assertIn("the level 'Storm Warden' has no", report['errors'][0]['error'])


class SplitHeadingsTest(unittest.TestCase):
    def lines(self):
        return [ln('Pier Lamp', heading=3, page=1, column='left', top=100), ln('Rock Lamp', heading=3, page=1, column='right', top=300),
                ln('Rock Lamp', heading=3, page=2, column='left', top=100)]

    def content(self, **boxes):
        side = lambda t, at: dict({'type': 'sidebar', 'title': t, 'content': []}, **({'_at': at} if at else {}))
        return [para('Lamps of the coast.'), head('Pier Lamp'), para('Lit at dusk.'), head('Rock Lamp'), para('Lit in fog.'),
                side('Pier Rules', boxes.get('a')), side('Coast Lore', boxes.get('b'))]

    def spec(self, **opt):
        return {'name': 'Lamps', 'page': 1, 'split_headings': dict({'category': 'spells', 'kind': 'lamp'}, **opt)}

    def test_boxes_go_to_the_last_heading_unless_the_plan_says(self):
        report = {'errors': [], 'left_out': []}
        keep, subs = convert_rules.split_at_headings(self.content(), self.lines(), self.spec(), report, 'Lamps')
        self.assertEqual([b['title'] for b in subs[1]['content'] if b['type'] == 'sidebar'], ['Pier Rules', 'Coast Lore'])
        keep, subs = convert_rules.split_at_headings(self.content(), self.lines(), self.spec(sidebars='entry'), report, 'Lamps')
        self.assertEqual([b['title'] for b in keep if b['type'] == 'sidebar'], ['Pier Rules', 'Coast Lore'])
        self.assertEqual([b['type'] for b in subs[1]['content']], ['paragraph'])

    def test_placed_boxes_go_with_the_heading_they_follow_in_reading_order(self):
        report = {'errors': [], 'left_out': []}
        # One box in the right column above the second heading (the first heading's text runs on
        # there); one above every heading (the section's own).
        content = self.content(a=[1, 2, 150.0], b=[1, 0, 40.0])
        keep, subs = convert_rules.split_at_headings(content, self.lines(), self.spec(sidebars='placed'), report, 'Lamps')
        self.assertEqual([b['title'] for b in subs[0]['content'] if b['type'] == 'sidebar'], ['Pier Rules'])
        self.assertEqual([b['title'] for b in keep if b['type'] == 'sidebar'], ['Coast Lore'])
        self.assertTrue(all('_at' not in b for x in subs for b in x['content']) and all('_at' not in x for x in subs))

    def test_shared_fields_and_a_name_of_its_own(self):
        report = {'errors': [], 'left_out': []}
        spec = self.spec(fields={'lore': 'Coast Lamps'}, rename={'Rock Lamp': 'Rock Lamp (Fog)'})
        _, subs = convert_rules.split_at_headings(self.content(), self.lines(), spec, report, 'Lamps')
        self.assertEqual([(x['name'], x['fields']) for x in subs],
                         [('Pier Lamp', {'kind': 'lamp', 'lore': 'Coast Lamps'}), ('Rock Lamp (Fog)', {'kind': 'lamp', 'lore': 'Coast Lamps'})])
        self.assertEqual(report['renamed'], [{'from': 'Rock Lamp', 'to': 'Rock Lamp (Fog)', 'in': 'Lamps'}])
        self.assertEqual(report['left_out'], ['Rock Lamp'])

    def test_a_boxs_column_is_the_one_it_starts_in(self):
        line = dict(ln('In a box', page=3, top=200), x0=320.0, column='full')
        self.assertEqual(convert_rules.reading_place(line, [300.0]), [3, 1, 200.0])
        self.assertEqual(convert_rules.reading_place(dict(line, x0=60.0), [300.0]), [3, 0, 200.0])
        self.assertEqual(convert_rules.reading_place(dict(line, column='right')), [3, 2, 200.0])


class DescribedUnderHeadingsTest(unittest.TestCase):
    def found(self):
        mk = lambda name: {'name': name, 'region': '1.1', 'section': 'Great Lamps', 'fields': {}}
        return [mk('Tower Lamp'), mk('Pier Lamp (Small)'), mk('Pier Lamp (Large)'), mk('Coast Mortar')]

    def content(self):
        return [para('Great lamps need a crew.'), head('Tower Lamp'), para('Seen for miles.'), head('Crews', 4), para('Three keepers.'),
                head('Pier Lamps'), para('Sold in two sizes.'), head('Mortar'), para('Fires flares.'), head('Rules'), para('Light them at dusk.')]

    def test_text_under_a_heading_that_names_an_item_moves_to_it(self):
        found, content, report = self.found(), self.content(), {'errors': [], 'left_out': []}
        plan = {'shared_labels': {'Pier Lamps': ['Pier Lamp (Small)', 'Pier Lamp (Large)'], 'Mortar': ['Coast Mortar']}}
        convert_rules.describe_items(found, [('Great Lamps', content, 'headings')], plan, report)
        self.assertEqual(report['errors'], [])
        self.assertEqual(found[0]['content'], [para('Seen for miles.'), head('Crews', 4), para('Three keepers.')])
        self.assertEqual(found[1]['content'], [head('Pier Lamps', 2), para('Sold in two sizes.')])     # shared: its heading kept
        self.assertEqual(found[1]['content'], found[2]['content'])
        self.assertEqual(found[3]['content'], [para('Fires flares.')])                                 # one item, named otherwise
        self.assertEqual(content, [para('Great lamps need a crew.'), head('Rules'), para('Light them at dusk.')])
        self.assertEqual(report['left_out'], ['Tower Lamp', 'Mortar'])
        self.assertEqual(report['headings_kept'], [{'entry': 'Great Lamps', 'heading': 'Rules', 'items': 0}])

    def test_without_the_mode_headings_stay(self):
        found, content, report = self.found(), self.content(), {'errors': [], 'left_out': []}
        convert_rules.describe_items(found, [('Great Lamps', content, True)], {}, report)
        self.assertEqual(len(content), len(self.content()))
        self.assertNotIn('content', found[0])


class ItemNamesTest(unittest.TestCase):
    COLS = ['Lamp', 'Price', 'Qualities and Flaws']
    SPEC = {'kind': 'lamp', 'fields': {'Price': 'price', 'Qualities and Flaws': 'qualities'}}

    def test_a_mark_on_the_name_points_at_its_footnote(self):
        report = {'errors': [], 'left_out': []}
        got = items.item_rows(self.COLS, [['Horn Lamp*', '1 GC', 'Dim'], ['Brass Lamp', '2 GC', 'Bright']], self.SPEC,
                              {'*': 'Sold with a wick.'}, report, 'here')
        self.assertEqual(report['errors'], [])
        self.assertEqual((got[0]['name'], got[0]['fields']['notes']), ('Horn Lamp', ['Sold with a wick.']))
        self.assertNotIn('notes', got[1]['fields'])

    def test_a_mark_on_the_name_and_on_its_group_gives_the_note_once(self):
        report = {'errors': [], 'left_out': []}
        got = items.item_rows(self.COLS, [['', 'PIER LAMPS*', ''], ['Horn Lamp*', '1 GC', 'Dim']], self.SPEC,
                              {'*': 'Sold with a wick.'}, report, 'here')
        self.assertEqual(got[0]['fields']['notes'], ['Sold with a wick.'])

    def test_a_band_set_at_the_left_heads_the_rows_below(self):
        report = {'errors': [], 'left_out': []}
        got = items.item_rows(self.COLS, [['PIER', '', ''], ['Horn Lamp', '1 GC', 'Dim'], ['TOWER', '', ''], ['Great Lamp', '9 GC', 'Bright']],
                              self.SPEC, {}, report, 'here')
        self.assertEqual([(i['name'], i['fields']['group']) for i in got], [('Horn Lamp', 'Pier'), ('Great Lamp', 'Tower')])
        self.assertIsNone(items.group_row(['Horn Lamp', '', '']))      # not in capitals: an item with empty cells
        self.assertIsNone(items.group_row(['PIER', '']))               # two columns: a name and nothing

    def test_the_two_handed_mark_is_read_without_its_bracket(self):
        report = {'errors': [], 'left_out': []}
        got = items.item_rows(self.COLS, [['(2H Great Lamp', '9 GC', 'Bright'], ['(2H) Pole Lamp', '3 GC', 'Dim']], self.SPEC, {}, report, 'here')
        self.assertEqual([(i['name'], i['fields'].get('two_handed')) for i in got], [('Great Lamp', True), ('Pole Lamp', True)])


if __name__ == '__main__':
    unittest.main()
