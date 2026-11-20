"""Tests for what a field manual of weapons, mounts and hirelings needed: entries split at bold
labels, item rows listed twice, marks inside a list, shared descriptions, a timeline's eras, a
profile whose second half sits beside it, roll tables flowed down a box's columns, a standfirst
over the columns, and a footnote in a ruled row of its own. All on invented lines and pages.

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

import convert_rules  # noqa: E402
import creatures  # noqa: E402
import entry_text  # noqa: E402
import items  # noqa: E402
import pdf_layout  # noqa: E402

try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    HAVE_LIBS = True
except ImportError:  # pragma: no cover
    HAVE_LIBS = False


def para(text):
    return {'type': 'paragraph', 'text': text}


def head(text, level=3):
    return {'type': 'heading', 'level': level, 'text': text}


class SplitAtLabelsTest(unittest.TestCase):
    SPEC = {'name': 'Lamp Options', 'page': 1,
            'split_labels': {'category': 'qualities', 'name_flags': {'rated': 'Rating'},
                             'names': {'Hooded': 'lamp-quality', 'Glare (Rating)': 'lamp-quality', 'Leaky': 'lamp-flaw'}}}

    def content(self):
        return [para('Some lamps do more than light a room.'), head('New Qualities'),
                para('**Hooded:** The light shows one way only.'),
                para('**Glare (Rating):** Dazzles those who look at it.'),
                para('**Close:** Add the Rating to the dazzle.'), para('**Far:** Halve it.'),
                para('**Leaky:** Drips oil on the keeper.'), head('Old Lamps'), para('Old lamps are sold by weight.')]

    def lines(self):
        texts = ['Some lamps do more than light a room.', 'New Qualities', 'Hooded: The light shows one way only.',
                 'Glare (Rating): Dazzles those who look at it.', 'Close: Add the Rating to the dazzle.',
                 'Far: Halve it.', 'Leaky: Drips oil on the keeper.', 'Old Lamps', 'Old lamps are sold by weight.']
        return [{'text': t, 'page': 1 if k < 4 else 2, 'heading': 3 if t in ('New Qualities', 'Old Lamps') else None}
                for k, t in enumerate(texts)]

    def test_each_named_label_is_an_entry_with_its_own_cases(self):
        report = {'errors': [], 'left_out': []}
        keep, subs = convert_rules.split_at_labels(self.content(), self.lines(), self.SPEC, report, 'Lamp Options')
        self.assertEqual(report['errors'], [])
        self.assertEqual([b['text'] for b in keep], ['Some lamps do more than light a room.', 'New Qualities',
                                                     'Old Lamps', 'Old lamps are sold by weight.'])
        self.assertEqual([(s['name'], s['kind'], s['page'], s['fields']['rated']) for s in subs],
                         [('Hooded', 'lamp-quality', 1, False), ('Glare (Rating)', 'lamp-quality', 1, True),
                          ('Leaky', 'lamp-flaw', 2, False)])
        self.assertEqual([b['text'] for b in subs[1]['content']],
                         ['Dazzles those who look at it.', '**Close:** Add the Rating to the dazzle.', '**Far:** Halve it.'])
        self.assertEqual(report['left_out'], ['Hooded', 'Glare (Rating)', 'Leaky'])       # the names, said once

    def test_a_name_with_no_paragraph_is_an_error(self):
        report = {'errors': [], 'left_out': []}
        spec = dict(self.SPEC, split_labels=dict(self.SPEC['split_labels'], names=['Hooded', 'Shuttered']))
        convert_rules.split_at_labels(self.content(), self.lines(), spec, report, 'Lamp Options')
        self.assertIn("no paragraph is labelled 'Shuttered'", report['errors'][0]['error'])


class ItemRowsTest(unittest.TestCase):
    COLS = ['Item', 'Price', 'Qualities and Flaws']
    FIELDS = {'Price': 'price', 'Qualities and Flaws': 'qualities'}

    def rows(self):
        return [['', 'PIER LAMPS', ''], ['Wick', '1/–', 'Slow 2*, Bright'], ['Jug', '2/–', '–'],
                ['', 'TOWER LAMPS', ''], ['Wick', '1/–', 'Slow 2*, Bright'], ['Lens', '9 GC', 'Bright**']]

    def test_a_mark_inside_a_list_points_at_its_footnote(self):
        report = {'errors': [], 'left_out': []}
        got = items.item_rows(self.COLS, self.rows()[:3], {'kind': 'lamp', 'fields': self.FIELDS},
                              {'*': 'Burns down by the hour.'}, report, 'here')
        self.assertEqual(report['errors'], [])
        self.assertEqual(got[0]['fields']['qualities'], ['Slow 2', 'Bright'])
        self.assertEqual(got[0]['fields']['notes'], ['Burns down by the hour.'])

    def test_an_item_listed_again_under_another_group_is_one_item(self):
        report = {'errors': [], 'left_out': []}
        spec = {'kind': 'lamp', 'fields': self.FIELDS, 'listed_again': ['Tower Lamps/Wick'],
                'marks_without_notes': ['Lens']}
        got = items.item_rows(self.COLS, self.rows(), spec, {'*': 'Burns down by the hour.'}, report, 'here')
        self.assertEqual(report['errors'], [])
        self.assertEqual([(i['name'], i['fields']['group']) for i in got],
                         [('Wick', 'Pier Lamps, Tower Lamps'), ('Jug', 'Pier Lamps'), ('Lens', 'Tower Lamps')])
        self.assertEqual(report['listed_again'], [{'where': 'here', 'item': 'Wick', 'group': 'Tower Lamps'}])
        self.assertIn('Wick 1/– Slow 2*, Bright', report['left_out'])
        # The book prints no "**" footnote: the plan says so, the mark stays, and the report tells.
        self.assertEqual(got[2]['fields']['qualities'], ['Bright**'])
        self.assertEqual(len(report['excused']), 1)
        self.assertIn("'Lens' is marked '**'", report['excused'][0])

    def test_a_mark_with_no_footnote_is_still_an_error_unless_the_plan_names_it(self):
        report = {'errors': [], 'left_out': []}
        items.item_rows(self.COLS, self.rows()[3:], {'kind': 'lamp', 'fields': self.FIELDS},
                        {'*': 'Burns down by the hour.'}, report, 'here')
        self.assertEqual(len(report['errors']), 1)
        self.assertIn("'Lens' is marked '**'", report['errors'][0]['error'])

    def test_listed_again_with_no_first_listing_is_an_error(self):
        report = {'errors': [], 'left_out': []}
        items.item_rows(self.COLS, self.rows()[3:5], {'kind': 'lamp', 'fields': self.FIELDS,
                                                      'listed_again': ['Tower Lamps/Wick']}, {'*': 'x'}, report, 'here')
        self.assertIn('no row above it has that name', report['errors'][0]['error'])

    def test_a_row_another_chapter_has_given_is_left_out_and_said(self):
        report = {'errors': [], 'left_out': []}
        spec = {'kind': 'lamp', 'fields': self.FIELDS, 'listed_elsewhere': ['Pier Lamps/Jug']}
        got = items.item_rows(self.COLS, self.rows()[:3], spec, {'*': 'Burns down by the hour.'}, report, 'here')
        self.assertEqual([i['name'] for i in got], ['Wick'])
        self.assertEqual(report['listed_again'][0]['first'], 'in another chapter')
        self.assertIn('Jug 2/– –', report['left_out'])
        self.assertNotIn('Pier Lamps', report['left_out'])        # the group still has the wick

    def test_a_group_whose_only_row_is_given_elsewhere_is_left_out_with_it(self):
        report = {'errors': [], 'left_out': []}
        spec = {'kind': 'lamp', 'fields': self.FIELDS, 'listed_elsewhere': ['Tower Lamps/Lens']}
        rows = self.rows()[:3] + [['', 'TOWER LAMPS', ''], ['Lens', '9 GC', 'Bright']]
        got = items.item_rows(self.COLS, rows, spec, {'*': 'Burns down by the hour.'}, report, 'here')
        self.assertEqual([i['name'] for i in got], ['Wick', 'Jug'])
        self.assertEqual(report['left_out'][-2:], ['Lens 9 GC Bright', 'Tower Lamps'])


class DescribeItemsTest(unittest.TestCase):
    def found(self):
        mk = lambda name, region, section, group: {'name': name, 'region': region, 'section': section,
                                                   'fields': {'group': group}}
        return [mk('Lantern', '1.1', 'Pier Lamps', 'Pier'), mk('Lantern', '2.1', 'Tower Lamps', 'Tower'),
                mk('Wick', '1.1', 'Pier Lamps', 'Pier'), mk('Spool', '1.1', 'Pier Lamps', 'Pier')]

    def test_a_label_two_renamed_items_share_goes_to_the_one_in_its_own_section(self):
        found, report = self.found(), {'errors': [], 'left_out': []}
        plan = {'rename': {'2.1/Tower/Lantern': 'Lantern (Tower)'}}
        tower = [para('**Lantern:** Lights the stair.')]
        pier = [para('**Lantern:** Lights the planks.')]
        convert_rules.describe_items(found, [('Tower Lamps', tower), ('Pier Lamps', pier)], plan, report)
        self.assertEqual(report['errors'], [])
        self.assertEqual(found[1]['name'], 'Lantern (Tower)')
        self.assertEqual(found[1]['content'], [para('Lights the stair.')])
        self.assertEqual(found[0]['content'], [para('Lights the planks.')])
        self.assertEqual((tower, pier), ([], []))

    def test_one_description_of_several_items_goes_to_each_label_and_all(self):
        found, report = self.found()[2:], {'errors': [], 'left_out': []}
        text = [para('**Wick and Spool:** Sold together by the yard.'), para('**Note:** Keep them dry.')]
        convert_rules.describe_items(found, [('Pier Lamps', text)], {'shared_labels': {'Wick and Spool': ['Wick', 'Spool']}}, report)
        self.assertEqual([i['content'] for i in found], [[para('**Wick and Spool:** Sold together by the yard.')]] * 2)
        self.assertEqual(text, [para('**Note:** Keep them dry.')])
        self.assertEqual(report['descriptions_shared'], [{'label': 'Wick and Spool', 'items': ['Wick', 'Spool']}])
        self.assertEqual([k['label'] for k in report['labels_kept']], ['Note'])


class OwnSlugTest(unittest.TestCase):
    def test_a_slug_that_takes_the_sources_code_must_not_be_another_chapters(self):
        taken = {'trappings': {'wick'}, convert_rules.OWN: {'trappings': {'wick-test': 'ch2'}}}
        report = {'errors': []}
        slug = convert_rules.free_slug('wick', 'trappings', 'Wick', {'source': 'TEST', 'chapter': 'ch5'}, taken, set(), report)
        self.assertEqual(slug, 'wick-test')
        self.assertIn('TEST ch2 already has an entry with this slug', report['errors'][0]['error'])

    def test_reimporting_the_chapter_itself_is_fine(self):
        taken = {'trappings': {'wick'}, convert_rules.OWN: {'trappings': {'wick-test': 'ch5'}}}
        report = {'errors': []}
        convert_rules.free_slug('wick', 'trappings', 'Wick', {'source': 'TEST', 'chapter': 'ch5'}, taken, set(), report)
        self.assertEqual(report['errors'], [])


class TimelineErasTest(unittest.TestCase):
    def content(self, extra=()):
        return [para('The tower has stood for three ages.'), head('The Age of Tallow'), *extra, head('Year 12'),
                para('The first lamp is lit.'), head('The Age of Oil'), head('Year 90'), para('Oil comes by sea.'),
                para('The keepers form a guild.')]

    def test_an_era_heads_the_rows_below_it(self):
        report = {'errors': []}
        out = convert_rules.headings_to_rows(self.content(), ['Year', 'Event'], report, 'Timeline',
                                             ['The Age of Tallow', 'The Age of Oil'])
        self.assertEqual(report['errors'], [])
        table = out[-1]
        self.assertEqual(table['rows'], [['Year 12', 'The first lamp is lit.'],
                                         ['Year 90', 'Oil comes by sea. The keepers form a guild.']])
        self.assertEqual(table['groups'], [{'before': 0, 'text': 'The Age of Tallow'}, {'before': 1, 'text': 'The Age of Oil'}])

    def test_text_under_an_era_or_an_era_not_printed_is_an_error(self):
        report = {'errors': []}
        convert_rules.headings_to_rows(self.content([para('A dark time.')]), ['Year', 'Event'], report, 'Timeline',
                                       ['The Age of Tallow', 'The Age of Oil', 'The Age of Gas'])
        errors = ' | '.join(e['error'] for e in report['errors'])
        self.assertIn("'The Age of Tallow' is a band in the plan, but has text under it", errors)
        self.assertIn("no heading for the band 'The Age of Gas'", errors)


def line(*spans):
    spans = [{'text': t, 'bold': b, 'italic': False, 'size': 9.0} for t, b in
             [(s, False) if isinstance(s, str) else s for s in spans]]
    return {'text': ' '.join(s['text'] for s in spans), 'spans': spans, 'size': 9.0, 'bold': all(s['bold'] for s in spans)}


class ProfileBesideItselfTest(unittest.TestCase):
    def test_the_second_half_set_after_another_line_is_brought_up(self):
        lines = [line(('WORN OUT', True)), line(('M WS BS S T I Ag', True)), line('–1 –10 –10 –5 –5 –10 –10'),
                 line(('Skills:', True), 'Lower every Skill by 10'), line(('Dex Int WP Fel', True)), line('–10 – – –')]
        report = {'errors': [], 'left_out': []}
        p, after = creatures.box_profile(lines, report, 'Worn Out')
        self.assertEqual(report['errors'], [])
        self.assertEqual(list(p['characteristics']), ['M', 'WS', 'BS', 'S', 'T', 'I', 'Ag', 'Dex', 'Int', 'WP', 'Fel'])
        self.assertEqual(p['skills'], ['Lower every Skill by 10'])
        self.assertEqual(after, [])


class FieldRunOnTest(unittest.TestCase):
    def line(self, *spans):
        self.y = getattr(self, 'y', 100) + 12
        return dict(line(*spans), page=1, column='left', x0=50.0, x1=280.0, baseline=float(self.y), italic=False)

    def test_a_field_that_stops_on_a_word_that_cannot_end_it_runs_on(self):
        seg = [self.line(('Max:', True), '2'), self.line(('Tests:', True), 'Lamp Tests when beside a keeper with'),
               self.line('Steady'), self.line('You hold the lamp still in any wind.')]
        report = {}
        n, _, got = entry_text.top_fields(seg, {'max': 'max', 'tests': 'tests'}, report, 'Steady')
        self.assertEqual((n, got), (3, {'max': '2', 'tests': 'Lamp Tests when beside a keeper with Steady'}))
        self.assertEqual(report['field_lines_joined'][0]['label'], 'Tests')

    def test_a_field_that_ends_on_a_noun_does_not(self):
        seg = [self.line(('Tests:', True), 'Lamp Tests in a gale'), self.line('You hold the lamp still.')]
        n, _, got = entry_text.top_fields(seg, {'tests': 'tests'}, {}, 'Steady')
        self.assertEqual((n, got), (1, {'tests': 'Lamp Tests in a gale'}))


class FlowedTablesTest(unittest.TestCase):
    """A box titled ERRAND MAKER: an opening line across it, then PLACE TABLE down the left column
    and on into the right, where KEEPER TABLE follows it."""

    def lines(self):
        L, R = (70, 105), (310, 345)                       # (roll x, text x) of each column

        def ln(y, *cells, heading=None):
            words = [[w, x + 6 * k, x + 6 * k + 5] for x, text in cells for k, w in enumerate(text.split())]
            return {'text': ' '.join(t for _, t in cells), 'page': 1, 'baseline': float(y), 'box': '1.1',
                    'words': words, **({'heading': heading} if heading else {})}

        return [ln(60, (240, 'ERRAND MAKER'), heading=3),
                ln(75, (70, 'Roll for a place, then for the keeper who sends you there today.')),
                ln(100, (140, 'PLACE TABLE'), (R[0], '06–10'), (R[1], 'A tar shed.')),
                ln(115, (L[0], '1d10'), (L[1], 'Place')),
                ln(130, (L[0], '01–02'), (L[1], 'A long pier.'), (360, 'KEEPER TABLE')),
                ln(140, (L[1], 'A lamp room with'), (R[0], '1d10'), (R[1], 'Keeper')),
                ln(145, (L[0], '03–04')),
                ln(150, (L[1], 'a cracked lens.'), (R[0], '01–05'), (R[1], 'A tired warden.')),
                ln(165, (L[0], '05'), (L[1], 'An oil cellar.'), (R[0], '06–10'), (R[1], 'A sharp clerk.'))]

    def plan(self, n=2):
        specs = [{'slug': 'errand-places', 'title': 'Errand Places'}, {'slug': 'errand-keepers', 'title': 'Errand Keepers'}]
        return {'tables': {'1.1': {'flowed': specs[:n]}}}

    def test_each_table_is_read_down_the_columns(self):
        lines, plan, report = self.lines(), self.plan(), {'errors': [], 'left_out': []}
        regions = {'1.1': {'id': '1.1', 'kind': 'table', 'page': 1, 'columns': ['', 'PLACE TABLE'], 'rows': [['x', 'y']]}}
        convert_rules.flow_tables(regions, lines, plan, report)
        self.assertEqual(report['errors'], [])
        self.assertEqual((regions['1.1']['columns'], regions['1.1']['rows']),
                         (['1d10', 'Place'], [['01–02', 'A long pier.'], ['03–04', 'A lamp room with a cracked lens.'],
                                              ['05', 'An oil cellar.'], ['06–10', 'A tar shed.']]))
        self.assertEqual((regions['1.1.2']['columns'], regions['1.1.2']['rows']),
                         (['1d10', 'Keeper'], [['01–05', 'A tired warden.'], ['06–10', 'A sharp clerk.']]))
        self.assertEqual(plan['tables']['1.1.2'], {'slug': 'errand-keepers', 'title': 'Errand Keepers'})
        self.assertEqual(plan['tables']['1.1']['slug'], 'errand-places')
        self.assertEqual(report['left_out'], ['PLACE TABLE', 'KEEPER TABLE'])
        # The box's title and opening line stay its own text; every other line belongs to a table.
        self.assertEqual([(l['text'], l.get('table')) for l in lines[:2]],
                         [('ERRAND MAKER', None), ('Roll for a place, then for the keeper who sends you there today.', None)])
        # A line the layout read across both columns is one line in each, with its own table.
        self.assertEqual([(l['text'], l['box']) for l in lines[2:6]],
                         [('PLACE TABLE', '1.1'), ('06–10 A tar shed.', '1.1'), ('1d10 Place', '1.1'),
                          ('01–02 A long pier.', '1.1')])
        self.assertEqual([(l['text'], l['box']) for l in lines[6:8]],
                         [('KEEPER TABLE', '1.1.2'), ('A lamp room with', '1.1')])
        self.assertTrue(all(l['table'] for l in lines[2:]))
        self.assertEqual({l['box'] for l in lines[2:]}, {'1.1', '1.1.2'})
        self.assertEqual(report['flowed_tables'], [{'box': '1.1', 'tables': [{'title': 'PLACE TABLE', 'rows': 4},
                                                                              {'title': 'KEEPER TABLE', 'rows': 2}]}])

    def test_a_different_number_of_tables_than_planned_is_an_error(self):
        report = {'errors': [], 'left_out': []}
        regions = {'1.1': {'id': '1.1', 'kind': 'table', 'page': 1, 'columns': [], 'rows': []}}
        convert_rules.flow_tables(regions, self.lines(), self.plan(1), report)
        self.assertIn('plans 1 tables, but the box holds 2', report['errors'][0]['error'])


class StandfirstTest(unittest.TestCase):
    def words(self, standfirst):
        col = lambda x0, x1: [{'x0': x0, 'x1': x1, 'baseline': 160.0 + 12 * k, 'size': 10.0} for k in range(30)]
        over = [{'x0': 50.0, 'x1': 551.0, 'baseline': 100.0 + 12 * k, 'size': 10.0} for k in range(standfirst)]
        return over + col(50, 292) + col(319, 551)

    def test_columns_are_found_under_an_opening_paragraph_set_across_them(self):
        words = self.words(3)
        self.assertEqual(pdf_layout.find_gutters(words, 609, three=False), [])
        self.assertEqual(pdf_layout.gutters_under_a_standfirst(words, 609, three=False), [306.0])

    def test_a_page_set_full_width_has_none(self):
        words = [{'x0': 50.0, 'x1': 551.0, 'baseline': 100.0 + 12 * k, 'size': 10.0} for k in range(30)]
        self.assertEqual(pdf_layout.gutters_under_a_standfirst(words, 609, three=False), [])

    def test_short_lines_under_full_width_text_are_not_a_column(self):
        # Full-width text, then a few short lines at the left (a stat block beside a picture).
        words = self.words(3)[:3] + [{'x0': 50.0, 'x1': 230.0, 'baseline': 160.0 + 12 * k, 'size': 10.0} for k in range(12)]
        self.assertEqual(pdf_layout.gutters_under_a_standfirst(words, 609, three=False), [])

    def test_a_block_at_the_top_left_and_another_at_the_bottom_right_are_not_columns(self):
        blk = lambda x0, x1, y: [{'x0': x0, 'x1': x1, 'baseline': y + 12.0 * k, 'size': 10.0} for k in range(12)]
        words = self.words(3)[:3] + blk(50, 230, 160) + blk(280, 551, 460)
        self.assertEqual(pdf_layout.gutters_under_a_standfirst(words, 609, three=False), [])

    def test_too_long_an_opening_is_not_a_standfirst(self):
        words = self.words(pdf_layout.STANDFIRST_LINES + 3)
        self.assertEqual(pdf_layout.gutters_under_a_standfirst(words, 609, three=False), [])


@unittest.skipUnless(HAVE_LIBS, 'reportlab and Pillow are needed to draw the invented pages')
class FootnoteRowTest(unittest.TestCase):
    def test_a_footnote_in_a_ruled_row_of_its_own_is_not_an_item(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, out = os.path.join(d, 'p.pdf'), os.path.join(d, 'l.json')
            c = canvas.Canvas(pdf, pagesize=A4)
            w, h = A4
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
            c.line(70, y, 350, y)                                # a rule above the footnote: a row of its own
            c.drawString(110, y - 13, '* Brass lamps burn twice as long in still air.')
            c.line(70, y - 18, 350, y - 18)
            for k in range(14):
                c.drawString(60, h - 300 - 11 * k, 'Keepers trim the wicks at dusk every day.')
                c.drawString(380, h - 110 - 11 * k, 'Gulls circle the tower.')
            c.showPage()
            c.save()
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pdf_layout.py'), pdf, '--pages', '1', '--boxes',
                                '--out', out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as f:
                doc = json.load(f)
        region = doc['regions'][0]
        self.assertEqual(region['rows'], [['Brass', '2 GC', '4 hours*'], ['Horn', '1 GC', '1 hour'], ['Great', '9 GC', '3 days']])
        self.assertIn('* Brass lamps burn twice as long in still air.',
                      [l['text'] for l in doc['lines'] if l.get('box') and not l.get('table')])


if __name__ == '__main__':
    unittest.main()
