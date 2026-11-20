"""Tests for table reading fixes found in a guide to lamp keepers: stacked tables, bands in
capitals read into several cells, words set off the line in a cell, a footnote under the last
row, and a chapter title over two lines. Invented pages and rows.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts')
sys.path.insert(0, SCRIPTS)

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False


class StackedTablesTest(unittest.TestCase):
    """Two tables one under the other with no rule between: the second's title and header ran
    into the last row of the first."""

    REGION = {'id': '1.1', 'page': 1, 'columns': ['Boat', 'Crew', 'Sail'],
              'rows': [['Gull', '4', '6'], ['Tern Boat', '2 HARBOUR Crew', '9 CARTS Pull'], ['Dray', '1', '3']]}
    PLAN = {'stacked': {'title': 'Harbour Carts', 'columns': ['Boat', 'Crew', 'Pull']}}

    def test_the_row_is_cleaned_and_the_rows_below_are_the_second_table(self):
        import convert_rules
        report = {'errors': []}
        first, second = convert_rules.unstack(self.REGION, self.PLAN, report, 'Lamps')
        self.assertEqual(report['errors'], [])
        self.assertEqual(first['rows'], [['Gull', '4', '6'], ['Tern', '2', '9']])
        self.assertEqual((second['columns'], second['rows']), (['Boat', 'Crew', 'Pull'], [['Dray', '1', '3']]))

    def test_no_such_row_is_an_error(self):
        import convert_rules
        report = {'errors': []}
        region = dict(self.REGION, rows=[['Gull', '4', '6'], ['Dray', '1', '3']])
        first, second = convert_rules.unstack(region, self.PLAN, report, 'Lamps')
        self.assertIsNone(second)
        self.assertIn("'Harbour Carts'", report['errors'][0]['error'])

    def test_a_table_the_plan_does_not_stack_is_left_alone(self):
        import convert_rules
        self.assertEqual(convert_rules.unstack(self.REGION, {}, {'errors': []}, 'Lamps'), (self.REGION, None))


class BandsInCapitalsTest(unittest.TestCase):
    def test_a_band_read_into_two_cells_heads_the_rows_below(self):
        import convert_rules
        region = {'id': '1.1', 'page': 1, 'columns': ['Lamp', 'Price', 'Enc', 'Burns', 'Light', 'Notes'],
                  'rows': [['', '', 'STORM', 'LAMPS', '', ''], ['Brass', '2', '1', '4 hours', 'Good', 'Heavy'],
                           ['', '', '', 'HAND LAMPS', '', ''], ['Horn', '1', '0', '1 hour', 'Poor', 'Light']]}
        report = {'errors': [], 'tables_to_confirm': []}
        b = convert_rules.table_block(region, 'Lights for Sale', {}, report, 'Lamps')
        self.assertEqual([r[0] for r in b['rows']], ['Brass', 'Horn'])
        self.assertEqual(report['group_rows'][0]['groups'], ['Storm Lamps', 'Hand Lamps'])

    def test_a_price_tables_band_may_start_in_the_first_cell(self):
        import items
        self.assertEqual(items.group_row(['LAMP', 'OILS', 'AND', '']), 'LAMP OILS AND')
        self.assertEqual(items.group_row(['', 'OILS', '', '']), 'OILS')
        self.assertIsNone(items.group_row(['Whale Oil', '2 GC', '1', 'Common']))
        self.assertIsNone(items.group_row(['OIL', '2 GC', '', '']))            # a price: an item


class EmptyLastColumnTest(unittest.TestCase):
    REGION = {'id': '1.1', 'page': 1, 'columns': ['Lamp', 'Price', ''],
              'rows': [['Brass', '2', ''], ['Horn', '1', '']]}

    def test_a_last_column_with_nothing_in_it_is_dropped_and_listed(self):
        import convert_rules
        report = {'errors': [], 'tables_to_confirm': []}
        b = convert_rules.table_block(self.REGION, 'Lights for Sale', {}, report, 'Lamps')
        self.assertEqual((b['columns'], b['rows']), (['Lamp', 'Price'], [['Brass', '2'], ['Horn', '1']]))
        self.assertEqual(report['empty_columns'], [{'entry': 'Lamps', 'region': '1.1', 'dropped': 1}])

    def test_a_column_with_one_cell_filled_stays(self):
        import convert_rules
        report = {'errors': [], 'tables_to_confirm': []}
        region = dict(self.REGION, rows=[['Brass', '2', ''], ['Horn', '1', 'dim']])
        b = convert_rules.table_block(region, 'Lights for Sale', {}, report, 'Lamps')
        self.assertEqual(len(b['columns']), 3)
        self.assertNotIn('empty_columns', report)


class ContinuedTableTest(unittest.TestCase):
    def regions(self, again):
        return {'1.1': {'id': '1.1', 'kind': 'table', 'columns': ['Lamp', 'Price'], 'rows': [['Brass', '2']]},
                '2.1': {'id': '2.1', 'kind': 'table', 'columns': again, 'rows': [['Horn', '1']]}}

    def test_a_header_printed_again_over_the_rest_is_left_out_once(self):
        import convert_rules
        regions, report = self.regions(['Lamp', 'Price']), {'left_out': []}
        merged = convert_rules.join_continued(regions, {'tables': {'1.1': {'continued_in': ['2.1']}}}, report)
        self.assertEqual(merged, {'2.1'})
        self.assertEqual(regions['1.1']['rows'], [['Brass', '2'], ['Horn', '1']])
        self.assertEqual(report['left_out'], ['Lamp Price'])

    def test_a_continuation_with_no_header_leaves_nothing_out(self):
        import convert_rules
        regions, report = self.regions(['', '']), {'left_out': []}
        convert_rules.join_continued(regions, {'tables': {'1.1': {'continued_in': ['2.1']}}}, report)
        self.assertEqual(report['left_out'], [])

    def test_a_box_that_is_not_there_is_remembered(self):
        import convert_rules
        plan = {'tables': {'1.1': {'continued_in': ['9.9']}}}
        self.assertEqual(convert_rules.join_continued(self.regions(['', '']), plan, {'left_out': []}), set())
        self.assertEqual(plan['_missing'], ['9.9'])


class BoxOverTheColumnsEndTest(unittest.TestCase):
    """A box that overlaps the last line of the column above it: the plan's "text_lines" gives
    that line back to the page, and the rest is still the box."""

    def lines(self):
        mk = lambda t, y, box=None, col='left': {'text': t, 'page': 1, 'baseline': y, 'x0': 60, 'x1': 280,
                                                 'column': col, 'box': box}
        return [mk('The wardens walk the piers at dusk and', 100), mk('trim every wick.', 112, '1.1', 'box'),
                mk('A LATE LAMP', 130, '1.1', 'box'), mk('One lamp is always lit late.', 142, '1.1', 'box'),
                mk('Gulls circle the tower.', 100, None, 'right')]

    def test_only_the_first_lines_join_the_page(self):
        import convert_rules
        report = {'errors': []}
        out = convert_rules.boxes_as_text(self.lines(), {'1.1': {'text_lines': 1}}, report, {'1': [300]})
        self.assertEqual(report['errors'], [])
        self.assertEqual([(l['text'], l['box']) for l in out],
                         [('The wardens walk the piers at dusk and', None), ('trim every wick.', None),
                          ('Gulls circle the tower.', None), ('A LATE LAMP', '1.1'), ('One lamp is always lit late.', '1.1')])
        self.assertEqual(out[1]['column'], 'left')


class CellTextTest(unittest.TestCase):
    def test_a_small_word_set_above_the_line_reads_where_it_stands(self):
        import pdf_layout
        words = [(240.0, 77.8, 84.9, '2H'), (241.8, 74.9, 77.9, '('), (241.8, 84.9, 87.9, ')'),
                 (241.8, 90.2, 120.1, 'Glaive')]
        self.assertEqual(pdf_layout.cell_text(words), '(2H) Glaive')

    def test_a_small_word_before_a_name_keeps_its_space(self):
        import pdf_layout
        words = [(530.1, 100.9, 110.8, '(2H)'), (535.4, 110.8, 139.0, 'Glaive')]
        self.assertEqual(pdf_layout.cell_text(words), '(2H) Glaive')

    def test_lines_of_a_cell_stay_in_order(self):
        import pdf_layout
        words = [(100.0, 10, 30, 'Brass'), (100.0, 33, 60, 'lamp,'), (112.0, 10, 40, 'heavy')]
        self.assertEqual(pdf_layout.cell_text(words), 'Brass lamp, heavy')


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the invented pages')
class PagesTest(unittest.TestCase):
    def layout(self, d, draw):
        pdf, out = os.path.join(d, 'p.pdf'), os.path.join(d, 'l.json')
        c = canvas.Canvas(pdf, pagesize=A4)
        draw(c, *A4)
        c.showPage()
        c.save()
        r = run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out) as f:
            return out, json.load(f)

    def test_a_footnote_under_the_last_row_is_not_part_of_it(self):
        def draw(c, w, h):
            c.drawImage(ImageReader(Image.new('RGB', (40, 40), (230, 220, 190))), 60, h - 230, 300, 150)
            c.setLineWidth(0.5)
            c.setFont('Helvetica-Bold', 9)
            for x, s in ((74, 'Lamp'), (174, 'Price'), (254, 'Burns')):
                c.drawString(x, h - 100, s)
            c.setFont('Helvetica', 9)
            y = h - 104
            for lamp, price, burns in (('Brass', '2 GC', '4 hours*'), ('Horn', '1 GC', '1 hour'), ('Great', '9 GC', '3 days')):
                c.line(70, y, 350, y)
                y -= 13
                c.drawString(74, y, lamp)
                c.drawString(174, y, price)
                c.drawString(254, y, burns)
                y -= 5
            c.drawString(74, y - 9, '*Brass lamps burn twice as long in still air.')       # no rule above it
            for k in range(14):
                c.drawString(60, h - 300 - 11 * k, 'Keepers trim the wicks at dusk every day.')
                c.drawString(380, h - 110 - 11 * k, 'Gulls circle the tower.')

        with tempfile.TemporaryDirectory() as d:
            _, doc = self.layout(d, draw)
        region = doc['regions'][0]
        self.assertEqual(region['rows'][-1], ['Great', '9 GC', '3 days'])
        self.assertIn('*Brass lamps burn twice as long in still air.',
                      [l['text'] for l in doc['lines'] if l.get('box') and not l.get('table')])

    def test_a_table_set_a_little_wider_than_its_panel(self):
        def draw(c, w, h):
            c.drawImage(ImageReader(Image.new('RGB', (40, 40), (230, 220, 190))), 80, h - 230, 300, 150)
            c.setLineWidth(0.5)
            c.setFont('Helvetica-Bold', 9)
            for x, s in ((84, 'Lamp'), (174, 'Price'), (254, 'Burns')):
                c.drawString(x, h - 100, s)
            c.setFont('Helvetica', 9)
            y = h - 104
            for lamp, price, burns in (('Brass', '2 GC', '4 hours'), ('Horn', '1 GC', '1 hour'), ('Great', '9 GC', '3 days')):
                c.line(72, y, 370, y)                                # the rules start left of the panel
                c.line(170, y, 170, y - 18)
                c.line(250, y, 250, y - 18)
                y -= 13
                c.drawString(84, y, lamp)
                c.drawString(174, y, price)
                c.drawString(254, y, burns)
                y -= 5
            c.line(72, y, 370, y)
            for k in range(14):
                c.drawString(60, h - 300 - 11 * k, 'Keepers trim the wicks at dusk every day.')
                c.drawString(400, h - 110 - 11 * k, 'Gulls circle the tower.')

        with tempfile.TemporaryDirectory() as d:
            _, doc = self.layout(d, draw)
        region = doc['regions'][0]
        self.assertEqual(region['columns'], ['Lamp', 'Price', 'Burns'])
        self.assertEqual(region['rows'], [['Brass', '2 GC', '4 hours'], ['Horn', '1 GC', '1 hour'], ['Great', '9 GC', '3 days']])

    def test_a_chapter_title_over_two_lines_is_left_out_whole(self):
        def draw(c, w, h):
            c.setFont('Helvetica-Bold', 30)
            c.drawString(60, h - 80, 'THE KEEPERS')
            c.drawString(90, h - 112, 'OF LAMPS')
            c.setFont('Helvetica', 9)
            for k in range(20):
                c.drawString(60, h - 160 - 11 * k, 'Keepers trim the wicks at dusk every day.')
                c.drawString(320, h - 160 - 11 * k, 'Gulls circle the tower all day long.')

        with tempfile.TemporaryDirectory() as d:
            layout, _ = self.layout(d, draw)
            plan, out = os.path.join(d, 'plan.json'), os.path.join(d, 'out')
            with open(plan, 'w') as f:
                json.dump({'source': 'TEST', 'chapter': 'ch1', 'intro': {'name': 'The Keepers of Lamps', 'kind': 'other'},
                           'entries': [], 'boxes': {}, 'relations': {}}, f)
            r = run('convert_rules.py', layout, '--plan', plan, '--out', out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(out, '_report.json')) as f:
                report = json.load(f)
            with open(os.path.join(out, 'the-keepers-of-lamps.json')) as f:
                entry = json.load(f)
        self.assertEqual(report['left_out'], ['THE KEEPERS', 'OF LAMPS'])
        self.assertTrue(entry['content'][0]['text'].startswith('Keepers trim the wicks'))


if __name__ == '__main__':
    unittest.main()
