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


if __name__ == '__main__':
    unittest.main()
