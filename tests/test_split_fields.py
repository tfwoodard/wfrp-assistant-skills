"""Tests for headings split into entries that carry labelled fields (a catalogue of lamp oils,
a list of jinxed lamps), on an invented page.

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

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {'source': 'TEST', 'chapter': 'ch4',
        'entries': [
            {'name': 'Catalogue of Oils', 'page': 1, 'kind': 'other',
             'split_headings': {'category': 'trappings', 'kind': 'oil',
                                'field_labels': ['Burn Time', 'Smoke']}},
            {'name': 'Jinxed Lamps', 'page': 1, 'kind': 'other',
             'split_headings': {'category': 'trappings', 'kind': 'jinxed-lamp', 'audience': 'gm',
                                'field_labels': ['Gift', 'Price'], 'text_labels': ['Description']}}],
        'whole_words': ['gutters'],
        'boxes': {'1.1': {'to': 'Whale Oil'}}, 'relations': {}}


def draw_page(path, smoke=True):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = [h - 110]

    def text(s, font='Helvetica', size=9, x=50, gap=12):
        c.setFont(font, size)
        c.drawString(x, y[0], s)
        y[0] -= gap

    def labelled(label, rest):
        c.setFont('Helvetica-Bold', 9)
        c.drawString(50, y[0], label + ':')
        c.setFont('Helvetica', 9)
        c.drawString(50 + c.stringWidth(label + ': ', 'Helvetica-Bold', 9), y[0], rest)
        y[0] -= 12

    c.setFont('Helvetica-Bold', 30)
    c.drawString(150, h - 70, 'THE LANTERN TRADES')
    text('Catalogue of Oils', 'Helvetica-Bold', 19, gap=16)
    text('Every keeper swears by a different oil.', gap=20)
    text('Whale Oil', 'Helvetica-Bold', 12, gap=13)
    labelled('Burn Time', 'Nine hours')
    if smoke:
        labelled('Smoke', 'Thin and grey')
    text('The lamp burns steadily in any wind and never once gut-', gap=12)
    text('ters.', gap=20)
    text('Tallow Oil', 'Helvetica-Bold', 12, gap=13)
    labelled('Burn Time', 'Four hours')
    labelled('Smoke', 'Thick and black')
    text('The lamp spits and smells of the kitchen.', gap=24)
    text('Jinxed Lamps', 'Helvetica-Bold', 19, gap=16)
    text('Some lamps are best left on the shelf.', gap=20)
    text('The Drowned Lamp', 'Helvetica-Bold', 12, gap=13)
    labelled('Gift', 'Burns under water')
    labelled('Price', 'Draws every gull for a mile')
    labelled('Description', 'A green glass lamp crusted with salt')
    text('that hums when the tide turns.', gap=18)
    text('Its keeper is never alone on the rocks.', gap=12)
    c.drawImage(ImageReader(Image.new('RGB', (40, 40), (230, 220, 190))), 314, h - 200, 240, 60)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(320, h - 156, 'RENDERING')
    c.setFont('Helvetica', 9)
    c.drawString(320, h - 170, 'Whale oil is rendered on the quay.')
    c.drawString(w / 2, 20, '1')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class SplitFieldsTest(unittest.TestCase):
    def convert(self, d, errors=0, args=(), **draw):
        pdf, layout, planf, out = (os.path.join(d, n) for n in ('p.pdf', 'layout.json', 'plan.json', 'out'))
        draw_page(pdf, **draw)
        r = run('pdf_layout.py', pdf, '--pages', '1', '--boxes', '--out', layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(planf, 'w') as f:
            json.dump(PLAN, f)
        r = run('convert_rules.py', layout, '--plan', planf, '--out', out, *args)
        self.assertEqual(r.returncode, 1 if errors else 0, r.stdout + r.stderr)
        with open(os.path.join(out, '_report.json')) as f:
            report = json.load(f)
        with open(os.path.join(out, '_records.json')) as f:
            records = {x['slug']: x for x in json.load(f)}
        return layout, out, report, records

    def entry(self, out, name):
        with open(os.path.join(out, name)) as f:
            return json.load(f)

    def test_each_split_entry_reads_its_labelled_lines_as_fields(self):
        with tempfile.TemporaryDirectory() as d:
            layout, out, report, records = self.convert(d)
            self.assertEqual(report['errors'], [])
            self.assertEqual({k: records['whale-oil'].get(k) for k in ('kind', 'burn_time', 'smoke')},
                             {'kind': 'oil', 'burn_time': 'Nine hours', 'smoke': 'Thin and grey'})
            self.assertEqual(records['tallow-oil']['burn_time'], 'Four hours')
            whale = self.entry(out, 'trappings--whale-oil.json')
            self.assertEqual([b['type'] for b in whale['content']], ['fields', 'paragraph', 'sidebar'])
            self.assertEqual(whale['content'][2]['title'], 'Rendering')       # the box sent "to" it
            self.assertEqual(report['questions'], [])                         # "gut-/ters": whole_words
            self.assertEqual([i['label'] for i in whale['content'][0]['items']], ['Burn Time', 'Smoke'])
            self.assertEqual(whale['content'][1]['text'], 'The lamp burns steadily in any wind and never once gutters.')
            r = run('check_coverage.py', layout, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_text_label_stays_prose_after_the_fields(self):
        with tempfile.TemporaryDirectory() as d:
            _, out, report, records = self.convert(d)
            lamp = self.entry(out, 'trappings--the-drowned-lamp.json')
            self.assertEqual([b['type'] for b in lamp['content']], ['fields', 'paragraph', 'paragraph'])
            self.assertEqual(lamp['content'][0]['items'][-1], {'label': 'Price', 'text': 'Draws every gull for a mile'})
            self.assertEqual(lamp['content'][1]['text'],
                             '**Description**: A green glass lamp crusted with salt that hums when the tide turns.')
            self.assertNotIn('description', records['the-drowned-lamp'])

    def test_split_entries_take_the_audience(self):
        with tempfile.TemporaryDirectory() as d:
            _, out, report, records = self.convert(d)
            self.assertEqual(records['the-drowned-lamp'].get('audience'), 'gm')
            self.assertEqual(self.entry(out, 'trappings--the-drowned-lamp.json').get('audience'), 'gm')
            self.assertNotIn('audience', records['whale-oil'])
            self.assertNotIn('audience', self.entry(out, 'jinxed-lamps.json'))

    def test_a_missing_label_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            _, out, report, records = self.convert(d, errors=1, smoke=False)
            self.assertEqual([e['error'] for e in report['errors']], ["Whale Oil: no 'Smoke' line"])

    def test_a_slug_another_chapter_of_the_source_holds_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            index = os.path.join(d, 'trappings.json')
            with open(index, 'w') as f:
                json.dump([{'slug': 'whale-oil', 'source': 'TEST', 'chapter': 'ch2'},
                           {'slug': 'tallow-oil', 'source': 'TEST', 'chapter': 'ch4'}], f)   # this chapter's own
            _, out, report, records = self.convert(d, errors=1, args=('--taken', f'trappings={index}'))
            self.assertEqual(len(report['errors']), 1)
            self.assertIn('trappings/whale-oil (Whale Oil): TEST ch2 already has', report['errors'][0]['error'])


class BannerRowsTest(unittest.TestCase):
    """A table whose title and a label over some columns were read as its first rows."""

    def test_banner_rows_come_off_the_top_and_the_title_is_no_banner(self):
        sys.path.insert(0, SCRIPTS)
        import convert_rules
        region = {'id': '1.1', 'columns': ['', '', ''],
                  'rows': [['', 'WICK', 'COSTS'], ['', 'Season', ''], ['Lamp', 'Summer', 'Winter'],
                           ['Gull', '2', '5']]}
        report = {'errors': []}
        cols, rows, banners, width, title = convert_rules.table_cells(
            region, '', {'title': 'Wick Costs', 'banner_rows': 2, 'header_row': True}, report, 'Lamps')
        self.assertEqual((cols, rows, width, title), (['Lamp', 'Summer', 'Winter'], [['Gull', '2', '5']], 3, 'Wick Costs'))
        self.assertEqual(banners, [{'text': 'Season', 'start': 1, 'span': 2}])
        self.assertEqual(report['errors'], [])


if __name__ == '__main__':
    unittest.main()
