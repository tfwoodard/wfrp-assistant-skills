"""Tests for convert_rules.py (and pdf_layout.py --boxes) on an invented two-page rules chapter the
test draws itself: no book text.

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
    import reportlab
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(TTFont('Vera', os.path.join(os.path.dirname(reportlab.__file__), 'fonts', 'Vera.ttf')))
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False

PLAN = {
    'source': 'TEST', 'chapter': 'ch5',
    'intro': {'name': 'Lamplight', 'kind': 'procedure', 'slug': 'lamplight-introduction'},
    'entries': [
        {'name': 'Trimming Wicks', 'page': 1, 'kind': 'procedure'},
        {'name': 'Smoked', 'page': 1, 'kind': 'condition', 'aliases': ['Smoked Condition']},
        {'name': 'Dread', 'heading': 'Dread (Rating)', 'page': 2, 'kind': 'psychology'},
        {'name': 'Wick Rot', 'page': 2, 'category': 'diseases', 'field_labels': ['Contraction', 'Duration']},
    ],
    'tables': {'1.1': {'slug': 'wick-lengths', 'title': 'Wick Lengths', 'about': 'How long a wick burns',
                       'roll': 'd10', 'roll_column': 0, 'continued_in': ['2.1']}},
}


def draw_chapter(path, unplanned=False):
    """Page 1: chapter title, an intro paragraph, "Trimming Wicks" (with a subheading, a list and a
    word split at a line end), a boxed ruled table, and the condition "Smoked". Page 2: the
    table's continuation in a box, a psychology trait and a disease."""
    img = os.path.join(os.path.dirname(path), 'parchment.png')
    Image.new('RGB', (40, 40), (230, 220, 190)).save(img)
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    L, R = 50, w / 2 + 6           # a two-column page with a 12-point gutter

    def text(x, y, s, font='Helvetica', size=9):
        c.setFont(font, size)
        c.drawString(x, y, s)

    def box_table(x0, top, rows, header):
        x1, height = x0 + 260, 22 + 14 * (len(rows) + (1 if header else 0))
        c.drawImage(img, x0, top - height, x1 - x0, height)
        y = top - 14
        if header:
            text(x0 + 10, y, 'Wick Lengths', 'Helvetica-Bold', 12)
            y -= 16
            text(x0 + 12, y, 'Roll', 'Helvetica-Bold')
            text(x0 + 70, y, 'Length', 'Helvetica-Bold')
            y -= 4
        for roll, length in rows:
            c.setLineWidth(0.5)
            c.line(x0 + 10, y, x1 - 10, y)
            y -= 10
            text(x0 + 12, y, roll)
            text(x0 + 70, y, length)
            y -= 4
        c.line(x0 + 10, y, x1 - 10, y)
        c.line(x0 + 64, top - (36 if header else 14), x0 + 64, y)

    text(w / 2 - 50, h - 85, 'Lamplight', 'Helvetica-Bold', 30)
    y = h - 115
    for s in ('Every keeper learns these rules before', 'climbing their first tower at dusk.'):
        text(L, y, s); y -= 11
    y -= 10
    text(L, y, 'Trimming Wicks', 'Helvetica-Bold', 18); y -= 16
    for s in ('A wick burns longer when trimmed. Keepers', 'trim every wick at dusk, and the tower-', 'top lamps first.'):
        text(L, y, s); y -= 11
    y -= 6
    text(L, y, 'Tools of Trimming', 'Helvetica-Bold', 12); y -= 14
    for s in ('• Shears for the wick', '• A cloth for the', '   soot', '• A taper'):
        text(L, y, s, 'Vera'); y -= 11        # a TrueType font, so the bullet reads back as "•"
    y -= 6
    for s in ('The great lamp burns until mid-', 'night; no keeper sleeps while it does.', 'Their towers stand tall at midnight.'):
        text(L, y, s); y -= 11
    if unplanned:
        y -= 6
        text(L, y, 'Spare Wicks', 'Helvetica-Bold', 18); y -= 16
        text(L, y, 'Keep three spare wicks.'); y -= 11
    box_table(L, y - 10, [('1–4', 'Short'), ('5–8', 'Long')], header=True)
    y = h - 115
    text(R, y, 'Smoked', 'Helvetica-Bold', 12); y -= 14
    for s in ('A Smoked keeper coughs and cannot', 'see far. Remove it with fresh air.'):
        text(R, y, s); y -= 11
    for i in range(10):
        text(R, y - 11 * i - 20, 'Keepers say fresh air helps everyone here.')
    c.showPage()

    box_table(L, h - 60, [('9–10', 'Endless')], header=False)
    y = h - 120
    text(L, y, 'Dread (Rating)', 'Helvetica-Bold', 12); y -= 14
    for s in ('A keeper with Dread fears the dark.', 'Test Cool to climb an unlit tower.'):
        text(L, y, s); y -= 11
    y -= 8
    text(L, y, 'Wick Rot', 'Helvetica-Bold', 12); y -= 14
    c.setFont('Helvetica-Bold', 9); c.drawString(L, y, 'Contraction:')
    text(L + 60, y, 'Handling old wicks.'); y -= 11
    c.setFont('Helvetica-Bold', 9); c.drawString(L, y, 'Duration:')
    text(L + 46, y, '1d10 days'); y -= 11
    for i in range(12):
        text(R, h - 120 - 11 * i, 'Rotten wicks smell of old tallow and ash.')
    c.showPage()
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True)


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the fixture PDF')
class ConvertRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(PLAN, f)

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, **draw):
        pdf = os.path.join(self.d, 'chapter.pdf')
        draw_chapter(pdf, **draw)
        layout = os.path.join(self.d, 'layout.json')
        r = run('pdf_layout.py', pdf, '--pages', '1-2', '--boxes', '--out', layout)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(self.d, 'out')
        r = run('convert_rules.py', layout, '--plan', os.path.join(self.d, 'plan.json'), '--out', out)
        with open(os.path.join(out, '_report.json')) as f:
            report = json.load(f)
        return r, out, layout, report

    def load(self, out, name):
        with open(os.path.join(out, name)) as f:
            return json.load(f)

    def test_a_box_sent_to_several_entries_is_copied_into_each(self):
        plan = dict(PLAN, boxes={'1.1': {'to': ['Trimming Wicks', 'Smoked']}})
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        r, out, layout, report = self.convert()
        self.assertEqual(r.returncode, 0, report['errors'])
        self.assertEqual([b['entry'] for b in report['box_placement']], ['Trimming Wicks', 'Smoked'])
        for slug in ('trimming-wicks', 'smoked'):
            self.assertEqual(sum(b['type'] == 'sidebar' for b in self.load(out, slug + '.json')['content']), 1)
        names = os.listdir(out)
        self.assertEqual(names.count('tables--wick-lengths.json'), 1)              # its table entry: once

    def test_layout_reads_boxes_and_a_continued_table(self):
        pdf = os.path.join(self.d, 'chapter.pdf')
        draw_chapter(pdf)
        layout = os.path.join(self.d, 'layout.json')
        run('pdf_layout.py', pdf, '--pages', '1-2', '--boxes', '--out', layout)
        with open(layout) as f:
            doc = json.load(f)
        regions = {r['id']: r for r in doc['regions']}
        self.assertEqual(regions['1.1']['kind'], 'table')
        self.assertEqual(regions['1.1']['columns'], ['Roll', 'Length'])
        self.assertEqual(regions['1.1']['rows'], [['1–4', 'Short'], ['5–8', 'Long']])
        self.assertEqual(regions['2.1']['rows'], [['9–10', 'Endless']])         # continued, no header
        self.assertIsNotNone(doc['gutters']['1'])                                 # the box doesn't hide it

    def test_entries_sidebars_tables_and_fields(self):
        r, out, layout, report = self.convert()
        self.assertEqual(r.returncode, 0, report['errors'])
        rec = {x['slug']: x for x in self.load(out, '_records.json')}
        self.assertEqual(set(rec), {'lamplight-introduction', 'trimming-wicks', 'smoked', 'dread', 'wick-rot',
                                    'wick-lengths'})
        self.assertEqual(rec['smoked']['kind'], 'condition')
        self.assertEqual(rec['smoked']['aliases'], ['Smoked Condition'])
        self.assertEqual(rec['dread']['section'], 'Dread (Rating)')
        self.assertEqual(rec['wick-rot']['_category'], 'diseases')
        self.assertEqual(rec['wick-lengths']['_category'], 'tables')

        intro = self.load(out, 'lamplight-introduction.json')
        self.assertTrue(intro['content'][0]['text'].startswith('Every keeper'))
        self.assertIn('Lamplight', report['left_out'])                          # the chapter title

        e = self.load(out, 'trimming-wicks.json')
        kinds = [b['type'] for b in e['content']]
        self.assertEqual(kinds, ['paragraph', 'heading', 'list', 'paragraph', 'sidebar'])
        self.assertEqual(e['content'][1], {'type': 'heading', 'level': e['level'] + 1, 'text': 'Tools of Trimming'})
        self.assertEqual(e['content'][2]['items'], ['Shears for the wick', 'A cloth for the soot', 'A taper'])
        self.assertIn('tower-top lamps', e['content'][0]['text'])                 # a compound kept: hyphen-unresolved
        self.assertIn('until midnight;', e['content'][3]['text'])                 # split only to fit: joined
        self.assertEqual(report['dehyphenated'], [{'entry': 'Trimming Wicks', 'from': 'mid-night', 'to': 'midnight'}])
        table = e['content'][4]['content'][-1]
        self.assertEqual(table['rows'], [['1–4', 'Short'], ['5–8', 'Long'], ['9–10', 'Endless']])
        self.assertEqual(table['data'][2], {'roll': {'min': 9, 'max': 10}, 'length': 'Endless'})
        self.assertEqual([b['entry'] for b in report['box_placement']], ['Trimming Wicks'])

        d = self.load(out, 'diseases--wick-rot.json')
        self.assertEqual(d['fields'], {'contraction': 'Handling old wicks.', 'duration': '1d10 days'})
        t = self.load(out, 'tables--wick-lengths.json')
        self.assertEqual(t['fields'], {'about': 'How long a wick burns', 'roll': 'd10'})
        self.assertEqual(len(report['tables_to_confirm']), 1)

        cov = run('check_coverage.py', layout, out)
        self.assertEqual(cov.returncode, 0, cov.stdout)

    def test_an_unplanned_heading_at_entry_level_is_an_error(self):
        r, out, layout, report = self.convert(unplanned=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("'Spare Wicks'" in e['error'] for e in report['errors']), report['errors'])

    def test_a_planned_entry_not_found_is_an_error(self):
        plan = dict(PLAN, entries=PLAN['entries'] + [{'name': 'Soot', 'page': 2, 'kind': 'condition'}])
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        r, out, layout, report = self.convert()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no heading 'Soot' on page 2", [e['error'] for e in report['errors']])


if __name__ == '__main__':
    unittest.main()
