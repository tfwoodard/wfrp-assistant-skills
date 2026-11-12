"""Tests for pdf_outline.py, pdf_layout.py and check_coverage.py, on a PDF the test draws
itself from invented text (never commit a real book page, or any PDF).

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
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAVE_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAVE_REPORTLAB = False


def draw_book(path, labels=True):
    """A cover, then printed pages 1-3: chapter 1 on pages 1-2 (two columns, a running head,
    a page number, a bold label), chapter 2 on page 3. Every word is invented."""
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFont('Helvetica-Bold', 30)
    c.drawString(100, h / 2, 'Cover of the Lantern Book')
    c.showPage()

    def page(n, bookmark=None, title=None):
        c.setFont('Helvetica', 8)
        c.drawString(50, h - 25, 'THE LANTERN BOOK')        # running head
        c.drawString(w / 2, 20, str(n))                     # page number
        if bookmark:
            key = bookmark.replace(' ', '')
            c.bookmarkPage(key)
            c.addOutlineEntry(bookmark, key, level=0)
        if title:
            c.setFont('Helvetica-Bold', 20)
            c.drawString(50, h - 80, title)

    page(1, 'Chapter 1: Lamps and Wicks', 'Chapter 1: Lamps and Wicks')
    c.setFont('Helvetica-Bold', 13)
    c.drawString(50, h - 120, 'Wick Trimmer')
    c.setFont('Helvetica', 10)
    c.drawString(50, h - 140, 'Trimmers keep the lamps of the')
    c.drawString(50, h - 153, 'harbour burning through fog.')
    c.setFont('Helvetica-Bold', 10)
    c.drawString(50, h - 170, 'Skills:')
    c.setFont('Helvetica', 10)
    c.drawString(85, h - 170, 'Climb, Endurance')
    c.setFont('Helvetica-Bold', 13)
    c.drawString(w / 2 + 20, h - 120, 'Oil Carrier')
    c.setFont('Helvetica', 10)
    c.drawString(w / 2 + 20, h - 140, 'Carriers haul oil up the stairs.')
    c.showPage()
    page(2)
    c.setFont('Helvetica', 10)
    c.drawString(50, h - 80, 'Left column on the second page.')
    c.drawString(w / 2 + 20, h - 80, 'Right column on the second page.')
    c.showPage()
    page(3, 'Chapter 2: Smoke', 'Chapter 2: Smoke')
    c.setFont('Helvetica', 10)
    c.drawString(50, h - 120, 'Smoke rises.')
    c.showPage()
    if labels:
        c.addPageLabel(0, style='ROMAN_UPPER')
        c.addPageLabel(1, style='ARABIC', start=1)
    c.save()


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True)


@unittest.skipUnless(HAVE_REPORTLAB, 'reportlab is needed to draw the fixture PDF')
class PdfToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.pdf = os.path.join(self.d, 'book.pdf')
        draw_book(self.pdf)

    def tearDown(self):
        self.tmp.cleanup()

    # --- pdf_outline.py ---

    def test_outline_gives_chapters_with_printed_pages_from_labels(self):
        r = run('pdf_outline.py', self.pdf)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('page offset 1', r.stderr)
        ch = json.loads(r.stdout)
        self.assertEqual([(c['id'], c['title'], c['pages'], c['pdf_pages'], c['status']) for c in ch], [
            ('ch1', 'Chapter 1: Lamps and Wicks', '1-2', '2-3', 'not-imported'),
            ('ch2', 'Chapter 2: Smoke', '3-3', '4-4', 'not-imported')])

    def test_outline_offset_given_by_hand_wins(self):
        r = run('pdf_outline.py', self.pdf, '--page-offset', '0')
        self.assertEqual(json.loads(r.stdout)[0]['pages'], '2-3')

    def test_outline_without_labels_says_it_assumed_no_offset(self):
        pdf = os.path.join(self.d, 'nolabels.pdf')
        draw_book(pdf, labels=False)
        r = run('pdf_outline.py', pdf)
        self.assertIn('no page labels', r.stderr)
        self.assertEqual(json.loads(r.stdout)[0]['pages'], '2-3')

    # --- pdf_layout.py ---

    def layout(self, pages='1-2'):
        out = os.path.join(self.d, 'layout.json')
        r = run('pdf_layout.py', self.pdf, '--pages', pages, '--page-offset', '1', '--out', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out) as f:
            return json.load(f)

    def test_layout_reads_left_column_before_right(self):
        texts = [l['text'] for l in self.layout()['lines'] if not l['furniture']]
        self.assertEqual(texts, [
            'Chapter 1: Lamps and Wicks',
            'Wick Trimmer', 'Trimmers keep the lamps of the', 'harbour burning through fog.',
            'Skills: Climb, Endurance',
            'Oil Carrier', 'Carriers haul oil up the stairs.',
            'Left column on the second page.', 'Right column on the second page.'])

    def test_layout_marks_running_heads_and_page_numbers_as_furniture(self):
        furn = [(l['page'], l['text']) for l in self.layout()['lines'] if l['furniture']]
        self.assertEqual(sorted(furn), [(1, '1'), (1, 'THE LANTERN BOOK'), (2, '2'), (2, 'THE LANTERN BOOK')])

    def test_layout_headings_by_size_and_spans_by_style(self):
        doc = self.layout()
        self.assertEqual(doc['body_size'], 10.0)
        by = {l['text']: l for l in doc['lines']}
        self.assertEqual(by['Chapter 1: Lamps and Wicks']['heading'], 1)
        self.assertEqual(by['Wick Trimmer']['heading'], 2)
        self.assertNotIn('heading', by['Trimmers keep the lamps of the'])
        self.assertTrue(by['Wick Trimmer']['bold'])
        self.assertEqual([(s['text'], s['bold']) for s in by['Skills: Climb, Endurance']['spans']],
                         [('Skills:', True), ('Climb, Endurance', False)])
        self.assertEqual(by['Oil Carrier']['column'], 'right')

    def test_layout_narrow_gutter_running_head_small_caps_slant_and_icons(self):
        pdf = os.path.join(self.d, 'tight.pdf')
        c = canvas.Canvas(pdf, pagesize=A4)
        w, h = A4
        c.setFont('Helvetica', 7)
        c.drawString(w / 2 - 60, h - 25, 'LAMPS AND WICKS - KEEPERS')    # running head across the middle
        y = h - 80
        c.setFont('Helvetica-Bold', 18)                                   # large and small capitals, one baseline
        c.drawString(50, y, 'C')
        c.setFont('Helvetica-Bold', 12.6)
        c.drawString(50 + c.stringWidth('C', 'Helvetica-Bold', 18), y, 'AREER')
        gutter_l, gutter_r = w / 2 - 5, w / 2 + 5                         # a 10-point gutter
        for i in range(12):
            yy = y - 20 - i * 11
            c.setFont('Helvetica', 9)
            s = 'left words fill the column here'
            c.drawString(gutter_l - c.stringWidth(s, 'Helvetica', 9), yy, s)
            c.drawString(gutter_r, yy, 'right words fill this column too')
        t = c.beginText()
        t.setFont('Helvetica', 9)
        t.setTextTransform(1, 0, 0.25, 1, 60, y - 170)
        t.textOut('Slanted')
        c.drawText(t)
        c.setFont('ZapfDingbats', 7)
        c.drawString(120, y - 170, 'n')
        p = c.beginPath()
        p.moveTo(140, y - 170); p.lineTo(146, y - 170); p.lineTo(143, y - 164); p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.showPage()
        c.save()
        out = os.path.join(self.d, 'tight.json')
        r = run('pdf_layout.py', pdf, '--pages', '1', '--icon-fonts', 'Zapf', '--out', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out) as f:
            doc = json.load(f)
        self.assertIsNotNone(doc['gutters']['1'])
        body = [l for l in doc['lines'] if not l['furniture']]
        self.assertEqual(body[0]['text'], 'CAREER')
        self.assertEqual(body[0]['size'], 18.0)
        cols = [l['column'] for l in body if 'words' in l['text']]
        self.assertEqual(cols, ['left'] * 12 + ['right'] * 12)
        slant = next(l for l in body if l['text'] == 'Slanted')
        self.assertTrue(slant['italic'])
        self.assertEqual([(m['font'], m['text']) for m in doc['marks']], [('ZapfDingbats', 'n')])
        self.assertEqual([s['pts'] for s in doc['shapes']], [4])

    def test_layout_refuses_pages_outside_the_pdf(self):
        r = run('pdf_layout.py', self.pdf, '--pages', '3-9', '--page-offset', '1')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('outside', r.stderr)

    def test_layout_text_view(self):
        r = run('pdf_layout.py', self.pdf, '--pages', '1', '--page-offset', '1', '--text')
        self.assertIn('p1    L  H2  13.0 B  Wick Trimmer', r.stdout)
        self.assertIn('p1    R  H2  13.0 B  Oil Carrier', r.stdout)

    # --- check_coverage.py ---

    def entries(self, out, trimmer_text):
        os.makedirs(out, exist_ok=True)
        entries = {
            'wick-trimmer': {'name': 'Wick Trimmer', 'content': [
                {'type': 'paragraph', 'text': trimmer_text},
                {'type': 'fields', 'items': [{'label': 'Skills', 'text': 'Climb, Endurance'}]}]},
            'oil-carrier': {'name': 'Oil Carrier', 'content': [
                {'type': 'paragraph', 'text': 'Carriers haul oil up the stairs.'}]},
        }
        for slug, e in entries.items():
            with open(os.path.join(out, slug + '.json'), 'w') as f:
                json.dump(dict(e, slug=slug, source='TEST', chapter='ch1', page=1), f)
        with open(os.path.join(out, '_report.json'), 'w') as f:
            json.dump({'left_out': ['Chapter 1: Lamps and Wicks', 'Left column on the second page.',
                                    'Right column on the second page.']}, f)

    def test_coverage_passes_when_every_word_is_placed(self):
        self.layout()
        out = os.path.join(self.d, 'out')
        self.entries(out, 'Trimmers keep the lamps of the harbour burning through fog.')
        r = run('check_coverage.py', os.path.join(self.d, 'layout.json'), out)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('accounted for', r.stdout)

    def test_coverage_lists_a_lost_word_and_excuses_only_out_loud(self):
        self.layout()
        out = os.path.join(self.d, 'out')
        self.entries(out, 'Trimmers keep the lamps of the harbour burning.')
        layout = os.path.join(self.d, 'layout.json')
        r = run('check_coverage.py', layout, out)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing: 'fog' x1", r.stdout)
        self.assertIn('p1: harbour burning through fog.', r.stdout)
        self.assertIn("missing: 'through' x1", r.stdout)
        r = run('check_coverage.py', layout, out, '--ignore', 'fog', 'through')
        self.assertEqual(r.returncode, 0)
        self.assertIn("excused: 'fog' x1 (--ignore)", r.stdout)


if __name__ == '__main__':
    unittest.main()
