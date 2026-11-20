"""Tests for an unruled table whose last column wraps and whose rows open with a key set level
with any line of their text (a timeline), on invented lines.

Run: python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts'))

import convert_rules  # noqa: E402

HEADER = 'Tower Year Fleet Year Event'
COLUMNS = ['Tower Year', 'Fleet Year', 'Event']


def ln(page, y, *cells, heading=None):
    """A line of cells [(x, text)]: words 5 wide, 3 apart within a cell."""
    words = [[w, x + 8 * k, x + 8 * k + 5] for x, text in cells for k, w in enumerate(text.split())]
    text = ' '.join(t for _, t in cells)
    return {'text': text, 'page': page, 'baseline': float(y), 'column': 'full', 'x0': words[0][1], 'x1': words[-1][2],
            'size': 9.0, 'bold': False, 'italic': False, 'words': words, 'heading': heading,
            'spans': [{'text': text, 'bold': False, 'italic': False, 'size': 9.0}]}


def page(n, rows):
    return [ln(n, 60, (250, 'TOWER TIMELINE'), heading=5), ln(n, 75, (180, 'Keepers count from the first lamp.')),
            ln(n, 95, (60, 'Tower Year'), (130, 'Fleet Year'), (360, 'Event'))] + rows


def first():
    return page(1, [ln(1, 110, (200, 'The first lamp is lit on')),
                    ln(1, 116, (60, '-'), (130, '-40')),                       # the key, between its two lines
                    ln(1, 122, (200, 'the old rock.')),
                    ln(1, 140, (60, '1'), (130, '-39'), (200, 'The tower is raised.')),
                    ln(1, 158, (200, 'Oil comes by sea and the')),
                    ln(1, 170, (60, '12 to 20'), (130, '-28 to -20'), (200, 'keepers form a guild.'))])


def second():
    return page(2, [ln(2, 110, (60, '90'), (130, '50'), (200, 'A great storm.'))])


class KeyedTextTableTest(unittest.TestCase):
    def plan(self, **kw):
        return [dict({'page': 1, 'header': HEADER, 'columns': COLUMNS, 'keyed': True, 'title': 'Tower Timeline'}, **kw)]

    def table(self, lines):
        return next(l['block'] for l in lines if l.get('block'))

    def test_each_key_takes_the_lines_nearest_it(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out = convert_rules.text_tables(first(), self.plan(), report)
        self.assertEqual(report['errors'], [])
        self.assertEqual(self.table(out)['rows'],
                         [['-', '-40', 'The first lamp is lit on the old rock.'], ['1', '-39', 'The tower is raised.'],
                          ['12 to 20', '-28 to -20', 'Oil comes by sea and the keepers form a guild.']])
        self.assertEqual([l['text'] for l in out[:2]], ['TOWER TIMELINE', 'Keepers count from the first lamp.'])
        self.assertEqual(len(out), 3)
        self.assertEqual(report['tables_to_confirm'][0]['rows'], 3)

    def test_it_goes_on_under_the_same_title_and_header_said_once(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out = convert_rules.text_tables(first() + second(), self.plan(more=[2]), report)
        self.assertEqual(report['errors'], [])
        self.assertEqual(len(self.table(out)['rows']), 4)
        self.assertEqual(self.table(out)['rows'][-1], ['90', '50', 'A great storm.'])
        self.assertEqual(len(out), 3)                             # page 2's title, note and header are gone
        self.assertEqual(report['left_out'], ['TOWER TIMELINE', 'Keepers count from the first lamp.', HEADER])

    def test_it_stops_at_the_line_the_plan_names(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        lines = first() + [ln(1, 200, (60, 'After the storm the tower stood empty.'))]
        out = convert_rules.text_tables(lines, self.plan(ends_before='After the storm'), report)
        self.assertEqual(report['errors'], [])
        self.assertEqual(out[-1]['text'], 'After the storm the tower stood empty.')
        self.assertEqual(len(self.table(out)['rows']), 3)

    def test_a_missing_continuation_header_is_an_error(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        convert_rules.text_tables(first(), self.plan(more=[2]), report)
        self.assertIn('no header on page 2', report['errors'][0]['error'])

    def test_a_header_that_is_not_on_the_page_is_an_error(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        convert_rules.text_tables(first(), [dict(self.plan()[0], header='Tower Year Fleet Year Event Note',
                                                 columns=COLUMNS + ['Note'])], report)
        self.assertIn("no such line", report["errors"][0]["error"])


class SideBySideTest(unittest.TestCase):
    """A glossary set twice across the page: word and meaning, word and meaning."""
    HEAD = 'Word Meaning Word Meaning'

    def page_one(self):
        return [ln(1, 60, (250, 'KEEPER WORDS'), heading=5),
                ln(1, 95, (60, 'Word'), (130, 'Meaning'), (310, 'Word'), (380, 'Meaning')),
                ln(1, 110, (60, 'Arn'), (130, 'A lamp.'), (380, 'Oil that has')),
                ln(1, 116, (310, 'Dru')),                               # the right copy's key, between its lines
                ln(1, 122, (60, 'Bek'), (130, 'A wick, or the'), (380, 'gone thick.')),
                ln(1, 134, (130, 'keeper who trims it.')),
                ln(1, 150, (60, 'Cal'), (130, 'Fog.'), (310, 'Eth'), (380, 'A bell.'))]

    def page_two(self):
        return [ln(2, 95, (60, 'Word'), (130, 'Meaning')),
                ln(2, 97, (310, 'Word'), (380, 'Meaning')),             # the second copy's header, a line of its own
                ln(2, 110, (60, 'Fen'), (130, 'A stair.'), (310, 'Gol'), (380, 'A gull.'))]

    def plan(self, **kw):
        return [dict({'page': 1, 'header': self.HEAD, 'columns': ['Word', 'Meaning'], 'keyed': True, 'side_by_side': 2,
                      'title': 'Keeper Words'}, **kw)]

    def test_the_left_copy_is_read_down_then_the_right(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out = convert_rules.text_tables(self.page_one(), self.plan(), report)
        self.assertEqual(report['errors'], [])
        block = next(l['block'] for l in out if l.get('block'))
        self.assertEqual(block['rows'], [['Arn', 'A lamp.'], ['Bek', 'A wick, or the keeper who trims it.'], ['Cal', 'Fog.'],
                                         ['Dru', 'Oil that has gone thick.'], ['Eth', 'A bell.']])
        self.assertEqual(block['columns'], ['Word', 'Meaning'])
        self.assertEqual(report['left_out'], ['Word Meaning'])            # the header over the second copy

    def test_it_goes_on_where_a_copys_header_sits_on_its_own_line(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        out = convert_rules.text_tables(self.page_one() + self.page_two(), self.plan(more=[2]), report)
        self.assertEqual(report['errors'], [])
        block = next(l['block'] for l in out if l.get('block'))
        self.assertEqual(block['rows'][-2:], [['Fen', 'A stair.'], ['Gol', 'A gull.']])
        self.assertEqual(len(block['rows']), 7)
        self.assertEqual(sorted(report['left_out']), ['Word Meaning', 'Word Meaning', 'Word Meaning'])
        self.assertEqual(len(out), 2)

    def test_cells_that_start_in_too_few_places_are_an_error(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        lines = [self.page_one()[1], ln(1, 110, (60, 'Arn'), (130, 'A lamp.'))]
        convert_rules.text_tables(lines, self.plan(), report)
        self.assertIn('do not start at 4 places', report['errors'][0]['error'])


class BlocksTest(unittest.TestCase):
    """A roll table printed as three blocks across the page, each under the header again."""

    def lines(self):
        head = lambda col: dict(ln(1, 80, (60, 'Roll'), (130, 'Lamp'), (200, 'Keeper')), column=col)
        row = lambda col, y, r, a, b: dict(ln(1, y, (60, r), (130, a), (200, b)), column=col)
        return [ln(1, 50, (60, 'Roll for a name.')),
                head('left'), row('left', 92, '1', 'Arn', 'Bek'), row('left', 104, '2', 'Cal', 'Dru'),
                dict(ln(1, 60, (250, 'LAMP NAMES'), heading=5), column='middle'),
                head('middle'), row('middle', 92, '3', 'Eth', 'Fen'), row('middle', 104, '4', 'Gol', 'Hul'),
                head('right'), row('right', 92, '5', 'Ith', 'Jor'),
                ln(1, 200, (60, 'Keepers take the name they roll.'))]

    def plan(self, **kw):
        return [dict({'page': 1, 'header': 'Roll Lamp Keeper', 'columns': ['Roll', 'Lamp', 'Keeper'], 'rows': [2, 2, 1],
                      'title_line': 'LAMP NAMES', 'title': 'Lamp Names', 'roll_column': 0}, **kw)]

    def test_the_blocks_are_one_table_and_the_title_is_said_once(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        entries = []
        out = convert_rules.text_tables(self.lines(), self.plan(), report, entries)
        self.assertEqual(report['errors'], [])
        self.assertEqual([l['text'] for l in out if not l.get('block')], ['Roll for a name.', 'Keepers take the name they roll.'])
        block = out[1]['block']
        self.assertEqual(block['rows'], [['1', 'Arn', 'Bek'], ['2', 'Cal', 'Dru'], ['3', 'Eth', 'Fen'], ['4', 'Gol', 'Hul'], ['5', 'Ith', 'Jor']])
        self.assertEqual(report['left_out'], ['Roll Lamp Keeper', 'Roll Lamp Keeper', 'LAMP NAMES'])
        self.assertEqual(entries, [])

    def test_with_a_slug_it_is_an_entry_and_may_be_that_alone(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        entries = []
        out = convert_rules.text_tables(self.lines(), self.plan(slug='lamp-names', in_text=False), report, entries)
        self.assertEqual([l['text'] for l in out], ['Roll for a name.', 'Keepers take the name they roll.'])
        self.assertEqual((entries[0][0]['slug'], len(entries[0][1]['rows'])), ('lamp-names', 5))

    def test_fewer_headers_than_blocks_or_no_title_line_is_an_error(self):
        report = {'errors': [], 'left_out': [], 'tables_to_confirm': []}
        convert_rules.text_tables(self.lines(), self.plan(rows=[2, 2, 1, 1]), report)
        convert_rules.text_tables(self.lines(), self.plan(title_line='LAMPS'), report)
        self.assertIn('4 blocks planned, but the header is printed 3 times', report['errors'][0]['error'])
        self.assertIn("no line 'LAMPS' among its blocks", report['errors'][1]['error'])


if __name__ == '__main__':
    unittest.main()
