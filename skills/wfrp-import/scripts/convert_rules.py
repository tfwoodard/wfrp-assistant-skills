#!/usr/bin/env python3
"""Convert chapters of rules prose into rules entries, with their sidebars and tables.

    pdf_layout.py BOOK.pdf --pages 148-191 --boxes --out LAYOUT.json
    convert_rules.py LAYOUT.json --plan PLAN.json --out OUT_DIR [--taken rules=<rules/_index.json> ...]

PLAN.json (kept in Drive beside the source, never in the repo):

    {
      "source": "CRB", "chapter": "ch5",
      "entries": [
        {"name": "Tests", "page": 149, "kind": "procedure"},
        {"name": "Ablaze", "page": 169, "kind": "condition", "aliases": ["Ablaze Condition"]},
        {"name": "Fear", "heading": "Fear (Rating)", "page": 190, "kind": "psychology"},
        {"name": "Blood Rot", "page": 186, "category": "diseases",
         "field_labels": ["Contraction", "Incubation", "Duration", "Symptoms"]}
      ],
      "boxes": {
        "150.3": {"diagram": "Resolving Actions flowchart"},
        "151.1": {"entry": {"name": "Options: Fast SL", "kind": "procedure"}},
        "153.4": {"to": "Tests"}
      },
      "tables": {
        "152.2": {"slug": "outcomes", "title": "Outcomes Table", "about": "What each SL range means", "roll_column": null},
        "47.1": {"title": "Advance Costs", "banner": true, "header_row": true},
        "174.1": {"slug": "head-critical-wounds", "title": "Head Critical Wounds", "roll_column": 0,
                  "continued_in": ["175.1"]}
      },
      "text_tables": [{"page": 160, "header": "Wicks Owned Oil Cost", "columns": ["Wicks Owned", "Oil Cost"],
                       "rows": 4, "title": "Oil Costs"}],
      "relations": {"tests": [{"role": "adds-to", "to": "rules/tests"}],
                    "tables/oil-costs": [{"role": "adds-to", "to": "rules/oil-costs"}]}
    }

"relations" is keyed by slug, or by <category>/<slug> where two entries share a slug; a table's
can also go in its "tables" plan as "relations".

Entries. Each planned entry starts at a heading on its page whose words match
its name (or its "heading", when the book prints more: "Fear (Rating)"), and
runs until the next planned entry's heading. An entry is a rules entry (its
"kind": procedure, condition, psychology, glossary) unless it names another
"category" (diseases, lore), which keeps the plan's "kind" when it gives one
(lore: god, place...). "field_labels" read the text after those bold labels
("**Harbour Master**: ...", run together or a line each) into the entry's fields,
and a missing one is an error; the paragraph they're printed in becomes a fields
block, items in printed order, with any text before the first label kept. Smaller headings
inside it become heading blocks. A heading the plan doesn't place, at the size
of the current entry's own heading or larger, is an error: it would be a
sibling entry nobody decided on. An entry with no heading of its own (a
letter, say, that opens with an address) can instead start at the first line on
its page whose text begins with its "starts_at"; every heading inside it is then
a subheading. "subheadings" names lines inside an entry, printed at body size
(a letter's bold section names), to read as its deepest subheadings, and
"not_headings" ([{"page", "text"}]) lines printed large that are body text (a
signature); a line either names that isn't found is an error. An entry's
"headings_as_rows" ([heading column, text column]) makes its headings and the
text under each one table (a timeline: dates and events). Lines with no
letter or digit printed below body size (flourishes) are left out and listed
under `ornaments`. Text before the first planned entry (the
chapter's title page) is left out and listed, unless the plan gives an
"intro" entry ({"name", "kind"}) for it; the chapter's title (its largest
heading) is left out either way.

Boxes (pdf_layout.py --boxes). A box becomes a sidebar, under its own title
(its heading lines), in the entry whose text runs just above it on its page in
the columns it spans; with no text above it there, in the entry running into
the page. The plan
can send it to another entry ("to"), or a copy to each of several (a list),
make it an entry of its own ("entry"),
read it as the page's own text ("text": a tinted backdrop the layout took for a box),
or mark it a diagram ("diagram": a flowchart or picture with words, left out
and listed for transcription by hand). A box read as a ruled table becomes a
table block; a table the plan lists under "tables" is also written as an entry
of its own in tables/ (when it gives a "slug"), with `about` and, when it is a
roll table, its roll column's values as {"min", "max"}. The plan can also give
a table's "title", say its read header is a "banner" printed across the
columns, or that its first row is its "header_row", and name its "columns" (when the header
isn't printed or isn't read). A table's title printed inside its frame, read into the first
row's cells, is taken out of them (`titles_stripped`). A row with only its first cell filled,
in a table of three or more columns, heads the rows below it (a group: `group_rows`).
"continued_in" lists boxes
on later pages holding the rest of its rows, which join it. "fold": 2 reads a table
printed in two side-by-side halves (the same columns twice) down the left half, then the right;
with "fold_join" (and "header_row", the parts' labels printed above them) parts that share
their first column are joined on it instead, each part's other columns named "<label>: <column>";
"from_columns": N reads a box's unruled lines, set in N columns, as a table. A table printed without rules is
listed under "text_tables": its header line (the columns' words, together), its columns and how
many rows follow; each row is split at its widest gaps, and a row without a clear gap is an
error.

Writes per entry <slug>.json and <slug>.md (render_entry.py), with `_category`
in `_records.json` (rules or tables), and `_report.json`:

- `errors` (exit status 1): a planned entry not found, an unplanned sibling
  heading, a box the plan names that isn't there.
- `questions`: line-end hyphens kept (`hyphen-join` when the book prints the
  hyphenated word elsewhere, `hyphen-unresolved` when it prints neither form).
- `dehyphenated`: words split at a line end and joined without the hyphen,
  because the book prints them whole elsewhere; check_coverage.py credits them.
- `filled_down`: table cells printed once for several rows, copied into `data`.
- `tables_to_confirm`: every table, to show the Librarian before it is written.
- `diagrams`: boxes left out for transcription by hand.
- `box_placement`: which entry each box went to, for the Librarian to check.
- `titles_stripped`, `group_rows`: tables whose title came out of row 1, and their group rows.
- `folded_keys`: a "fold_join" table's key column as printed in its later parts, kept once.
- `left_out`: everything printed that no entry holds.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402
import items  # noqa: E402
import creatures  # noqa: E402
from entry_text import (blocks_from_lines, fix_case, merge_lines, norm, plain, slugify, split_row,  # noqa: E402
                        table_data, vocabulary)


SUBHEADING = 99      # the heading level given to a plan's "subheadings": below every printed level


def split_at_headings(content, lines, spec, report, where):
    """An entry's "split_headings" ({"category", "kind"}): each of its top subheadings, with the
    blocks under it, becomes an entry of its own (a list of weapon qualities); the text before
    the first stays the entry's. A "dividers" heading ({heading: kind}, "Armour Flaws") is no
    entry: it and its text stay the entry's, and the headings after it take its kind. Returns
    (the entry's content, the new entries). "name_flags" ({field: regex}) gives each new entry a
    field that is true when its name matches ({"rated": "Rating"} for "Armour (Rating)")."""
    opt = spec['split_headings']
    dividers = {norm(k): v for k, v in opt.get('dividers', {}).items()}
    kind, seen = opt.get('kind'), set()
    heads = [b['level'] for b in content if b['type'] == 'heading']
    if not heads:
        report['errors'].append({'error': f'{where}: split_headings, but the entry has no headings'})
        return content, []
    top = min(heads)
    keep, subs, after = [], [], 0
    for b in content:
        if b['type'] == 'heading' and b['level'] == top and norm(b['text']) in dividers:
            kind = dividers[norm(b['text'])]          # "Armour Flaws": the headings after it are flaws
            seen.add(norm(b['text']))
            keep.append(b)
            subs.append(None)
        elif b['type'] == 'heading' and b['level'] == top:
            hit = next((i for i, l in enumerate(lines) if i >= after and l.get('heading') and
                        norm(b['text']).startswith(norm(fix_case(plain(l['text']))))), None)
            if hit is None:
                report['errors'].append({'error': f'{where}: no page for the heading {b["text"]!r}'})
            page = lines[hit]['page'] if hit is not None else spec['page']
            after = hit + 1 if hit is not None else after
            subs.append({'name': b['text'], 'category': opt['category'], 'kind': kind,
                         'page': page, 'section': spec['name'], 'content': [],
                         'fields': dict({'kind': kind} if kind else {},
                                        **{f: bool(re.search(pat, b['text']))
                                           for f, pat in opt.get('name_flags', {}).items()})})
        elif subs and subs[-1] is None:
            keep.append(b)                            # a divider's own text stays the entry's
        elif subs:
            if b['type'] == 'heading':
                b = dict(b, level=b['level'] - (top - 2))
            subs[-1]['content'].append(b)
        else:
            keep.append(b)
    for d in set(dividers) - seen:
        report['errors'].append({'error': f'{where}: no divider heading {d!r}'})
    return keep, [x for x in subs if x]


def describe_items(found, describers, plan, report):
    """Paragraphs that open with an item's name as a bold label ("**Coat:** Protects ..."), in
    entries marked "describes_items", move to that item, without the label. A label naming no
    item stays where it is and is listed under `labels_kept`; two items of one name are an error,
    unless the plan's "rename" ({"<table>/<name>" or "<table>/<group>/<name>": new name})
    tells them apart."""
    for it in found:
        ren = plan.get('rename', {})
        new = ren.get(f'{it["region"]}/{it["fields"].get("group", "")}/{it["name"]}') or \
            ren.get(f'{it["region"]}/{it["name"]}')
        if new:
            report.setdefault('renamed', []).append({'region': it['region'], 'from': it['name'], 'to': new})
            it['name'] = new
    by_name = {}
    for it in found:
        by_name.setdefault(norm(it['name']), []).append(it)
    for key, its in by_name.items():
        if len(its) > 1:
            report['errors'].append({'error': f'{len(its)} items named {its[0]["name"]!r} '
                                              f'(tables {", ".join(i["region"] for i in its)}): rename them'})
    for where, content in describers:
        for b in list(content):
            lab = items.label(b['text']) if b['type'] == 'paragraph' else None
            if not lab:
                continue
            match = [it for it in found if items.same_item(it['name'], lab[0])]
            if len(match) == 1:
                match[0].setdefault('content', []).append({'type': 'paragraph', 'text': lab[1]})
                content.remove(b)
                report.setdefault('descriptions_moved', []).append(match[0]['name'])
                report['left_out'].append(lab[0])     # the label: the item's name again
            else:
                report.setdefault('labels_kept', []).append({'entry': where, 'label': lab[0],
                                                             'items': len(match)})


def add_entry(spec, out, records, plan, taken, used_slugs):
    """An entry made from part of another (a split heading, a price-table row): written and
    indexed like the plan's own."""
    cat, name = spec['category'], spec['name']
    fields = dict(spec.get('fields') or ({'kind': spec['kind']} if spec.get('kind') else {}))
    slug = spec.get('slug') or slugify(name)
    if slug in taken or (cat, slug) in used_slugs:     # a slug is one entry's within its category
        slug = f'{slug}-{plan["source"].lower()}'
    used_slugs.add((cat, slug))
    entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
             'section': spec['section'], 'page': spec['page'], 'level': 1, 'fields': fields,
             'content': spec['content']}
    if cat == 'rules':
        entry['kind'] = fields.get('kind', 'procedure')
    rel = plan.get('relations', {}).get(f'{cat}/{slug}') or plan.get('relations', {}).get(slug)
    if rel:
        entry['relations'] = rel
    out.append((cat, entry))
    rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
           'section': spec['section'], 'page': spec['page'], '_category': cat}
    rec.update(fields)
    if rel:
        rec['relations'] = rel
    records.append(rec)


def headings_to_rows(content, columns, report, where):
    """An entry's run of headings, each followed by its text (a timeline's dates, a glossary's
    terms), as one table with `columns` [heading, text]: each heading a row, its paragraphs joined
    in the second cell. Text before the first heading stays as it is; anything else under a
    heading (a list, a sidebar) is an error."""
    head = next((i for i, b in enumerate(content) if b['type'] == 'heading'), None)
    if head is None:
        report['errors'].append({'error': f'{where}: headings_as_rows, but the entry has no headings'})
        return content
    rows = []
    for b in content[head:]:
        if b['type'] == 'heading':
            rows.append([b['text'], ''])
        elif b['type'] == 'paragraph':
            rows[-1][1] = (rows[-1][1] + ' ' + b['text']).strip()
        else:
            report['errors'].append({'error': f'{where}: a {b["type"]} under {rows[-1][0]!r} '
                                              f'can\'t go in a row'})
    empty = [r[0] for r in rows if not r[1]]
    if empty:
        report['errors'].append({'error': f'{where}: no text under {", ".join(map(repr, empty))}'})
    block = {'type': 'table', 'title': '', 'columns': list(columns), 'rows': rows,
             'data': table_data(list(columns), rows, report, where, None)}
    return content[:head] + [block]


def page_column(line, gutters):
    """The column ("left", "middle", "right") a line sits in between a page's gutters, or
    "full" when it crosses one."""
    names = {1: ['left', 'right'], 2: ['left', 'middle', 'right']}.get(len(gutters))
    if not names:
        return 'full'
    edges = [float('-inf')] + list(gutters) + [float('inf')]
    for i, name in enumerate(names):
        if line['x0'] >= edges[i] and line['x1'] <= edges[i + 1]:
            return name
    return 'full'


def boxes_as_text(lines, boxes_plan, report, gutters=None):
    """Boxes the plan marks "text" (a tinted backdrop read as a box) are read as the page's
    columns: their lines lose the box and take the page column (from its `gutters`) they sit
    in, and the page is read again, top to bottom between its full-width lines, column by
    column from the left."""
    pages = {}
    for bid, bp in boxes_plan.items():
        if bp.get('text'):
            hit = [l for l in lines if l.get('box') == bid]
            if not hit:
                report['errors'].append({'error': f'the plan reads box {bid} as text, but it has no lines'})
            for l in hit:
                l['box'] = None
                l['column'] = page_column(l, (gutters or {}).get(str(l['page'])) or [])
                pages[l['page']] = True
    if not pages:
        return lines
    rank = {'full': -1, 'left': 0, 'middle': 1, 'right': 2}

    def key(l):
        fulls = [x['baseline'] for x in lines if x['page'] == l['page'] and x['column'] == 'full' and not x.get('box')]
        above = sum(1 for b in fulls if b < l['baseline'] or (b == l['baseline'] and l['column'] != 'full'))
        return (above, rank.get(l['column'], 2), l['baseline'], l['x0'])
    out = []
    for page in dict.fromkeys(l['page'] for l in lines):
        on = [l for l in lines if l['page'] == page]
        if page in pages:
            on = sorted([l for l in on if not l.get('box')], key=key) + [l for l in on if l.get('box')]
        out += on
    return out


def heading_runs(lines):
    """Index of each heading start -> (text, last index): a heading printed over two lines is one."""
    runs, i = {}, 0
    while i < len(lines):
        l = lines[i]
        if l.get('heading') and not l.get('box'):
            j, text = i, plain(l['text'])
            while (j + 1 < len(lines) and lines[j + 1].get('heading') == l['heading'] and
                   not lines[j + 1].get('box') and lines[j + 1]['column'] == l['column'] and
                   lines[j + 1]['page'] == l['page'] and
                   lines[j + 1]['baseline'] - lines[j]['baseline'] < 1.6 * l['size']):
                j += 1
                text += ' ' + plain(lines[j]['text'])
            runs[i] = (text, j)
            i = j + 1
        else:
            i += 1
    return runs


def box_parts(box_lines):
    """A box's lines -> (title, body lines, table lines): the title is its leading heading lines."""
    title, i = [], 0
    while i < len(box_lines) and box_lines[i].get('heading') and not box_lines[i].get('table'):
        title.append(plain(box_lines[i]['text']))
        i += 1
    body = [l for l in box_lines[i:] if not l.get('table')]
    return fix_case(' '.join(title)), body, [l for l in box_lines if l.get('table')]


def labelled_to_fields(content, labels):
    """Each paragraph holding the plan's bold labels ("**Contraction:** ... **Incubation:** ...")
    becomes a fields block, its items in printed order; text before the first label stays a
    paragraph. Neighbouring fields blocks join."""
    out = []
    for b in content:
        hits = []
        if b['type'] == 'paragraph':
            for lab in labels:
                m = re.search(r'\*{2,3}' + re.escape(lab) + r':?\*{2,3}:?\s*', b['text'])
                if m:
                    hits.append((m.start(), m.end(), lab))
        if not hits:
            out.append(b)
            continue
        hits.sort()
        if b['text'][:hits[0][0]].strip():
            out.append(dict(b, text=b['text'][:hits[0][0]].strip()))
        items = [{'label': lab, 'text': plain(b['text'][end:(hits[k + 1][0] if k + 1 < len(hits) else None)])}
                 for k, (_, end, lab) in enumerate(hits)]
        if out and out[-1]['type'] == 'fields' and not out[-1].get('title'):
            out[-1]['items'] += items
        else:
            out.append({'type': 'fields', 'title': '', 'items': items})
    return out


def strip_title(row, title):
    """The table's title, when its words lead cells of the first row ("Lamp Mishaps table
    Soot: ..." or "OILS BY Tallow" / "TOWER Rush"), taken out of them. Returns the row
    and whether the whole title was found; a title only partly there leaves the row alone."""
    want = [norm(w) for w in title.split()]
    out, k = list(row), 0
    for i, cell in enumerate(out):
        words = cell.split()
        n = 0
        while k < len(want) and n < len(words) and norm(words[n]) == want[k]:
            n, k = n + 1, k + 1
        if n:
            out[i] = ' '.join(words[n:])
        if k == len(want):
            return out, True
    return list(row), False


def table_block(region, title, plan_t, report, where):
    cols, rows, banners, width, title = table_cells(region, title, plan_t, report, where)
    plan_t = plan_t or {}
    groups, kept = [], []
    for r in rows:                    # a row with only its first cell filled heads the rows below
        if width > 2 and r and r[0].strip() and not any(c.strip() for c in r[1:]):
            groups.append({'before': len(kept), 'text': r[0].strip()})
        else:
            kept.append(r)
    if groups:
        rows = kept
        report.setdefault('group_rows', []).append({'entry': where, 'region': region['id'],
                                                    'groups': [g['text'] for g in groups]})
    names = cols if cols else [f'Column {i + 1}' for i in range(width)]
    block = {'type': 'table', 'title': title, 'columns': cols or [''] * width,
             'rows': rows, 'data': table_data(names, rows, report, where, plan_t.get('roll_column'))}
    if banners:
        block['banners'] = banners
    if groups:
        block['groups'] = groups
    report['tables_to_confirm'].append({'entry': where, 'region': region['id'], 'page': region['page'],
                                        'title': block['title'], 'columns': len(names), 'rows': len(rows)})
    return block


def table_cells(region, title, plan_t, report, where):
    """A table region's (columns, rows, banners, width, title) as its plan reads them: a cell
    holding two columns split ("split_column"), a banner, a header row, folded halves, a title
    printed in the first row, and the columns' names."""
    cols, rows = list(region.get('columns') or []), [list(r) for r in region['rows']]
    plan_t = plan_t or {}
    if plan_t.get('split_column'):
        sc = plan_t['split_column']
        cols, rows = items.split_column(cols, rows, sc['index'], sc['words'], report,
                                        f'{where}: table {region["id"]}')
    banners = []
    if plan_t.get('banner'):          # the header read is a banner printed across the columns
        text = ' '.join(c for c in cols if c.strip())
        start = next((i for i, c in enumerate(cols) if c.strip()), 0)
        banners.append({'text': text, 'start': start, 'span': len(cols) - start})
        cols = []
    labels = []
    if plan_t.get('header_row'):      # the first row read is the header (printed below a rule)
        labels = cols                 # what was read as the header is then each part's label
        cols, rows = rows[0], rows[1:]
    if plan_t.get('fold'):            # one table printed in side-by-side halves: read down each
        n = plan_t['fold']
        k = len(cols) // n
        if k == 0 or len(cols) != k * n or any(cols[i * k:(i + 1) * k] != cols[:k] for i in range(n)):
            report['errors'].append({'error': f'{where}: table {region["id"]} is not {n} copies of '
                                     f'one set of columns: {cols}'})
        elif plan_t.get('fold_join'):   # parts sharing their first column: one row per key
            names = [' '.join(c for c in labels[i * k:(i + 1) * k] if c.strip()) or f'Part {i + 1}'
                     for i in range(n)]
            if any([r[i * k] for r in rows] != [r[0] for r in rows] for i in range(n)):
                report['errors'].append({'error': f'{where}: table {region["id"]}: the {n} parts don\'t '
                                         f'share their first column'})
            else:
                # The key column printed once per part is kept once; the copies are listed.
                report.setdefault('folded_keys', []).append(
                    {'entry': where, 'region': region['id'],
                     'cells': [c for i in range(1, n) for c in [cols[i * k]] + [r[i * k] for r in rows]]})
                vals = cols[1:k]
                cols = [cols[0]] + [f'{nm}: {v}' for nm in names for v in vals]
                rows = [[r[0]] + [c for i in range(n) for c in r[i * k + 1:(i + 1) * k]] for r in rows]
        else:
            rows = [r[i * k:(i + 1) * k] for i in range(n) for r in rows]
            rows = [r for r in rows if any(c.strip() for c in r)]
            cols = cols[:k]
    width = max([len(cols)] + [len(r) for r in rows])
    title = plan_t.get('title') or title
    if title and rows:                # a title printed inside the table's frame, read into row 1
        rows[0], stripped = strip_title(rows[0], title)
        if stripped:
            report.setdefault('titles_stripped', []).append({'entry': where, 'region': region['id'],
                                                             'title': title})
    if plan_t.get('columns'):         # the columns' names, when the header isn't printed or read
        if len(plan_t['columns']) != width:
            report['errors'].append({'error': f'{where}: table {region["id"]} has {width} columns, '
                                     f'the plan names {len(plan_t["columns"])}'})
        else:
            cols = list(plan_t['columns'])
    if not any(c.strip() for c in cols):
        cols = []
    return cols, rows, banners, width, title


def text_tables(lines, plans, report):
    """Tables printed without rules, as the plan describes them: the header line (its words, which
    must be the columns' words), then `rows` lines, each split into cells at its widest gaps. The
    lines are replaced by one carrying the table block. A row whose gap is no wider than the gaps
    between its words is not a table row: an error."""
    for t in plans:
        where = f'text table {t["header"]!r} on page {t["page"]}'
        i = next((k for k, l in enumerate(lines) if l['page'] == t['page'] and not l.get('block') and
                  norm(plain(l['text'])) == norm(t['header'])), None)
        if i is None:
            report['errors'].append({'error': f'{where}: no such line'})
            continue
        if norm(' '.join(t['columns'])) != norm(t['header']):
            report['errors'].append({'error': f'{where}: the columns {t["columns"]} are not its words'})
            continue
        run = lines[i:i + 1 + t['rows']]
        rows = []
        for l in run[1:]:
            w = l['words']
            gaps = sorted(w[k + 1][1] - w[k][2] for k in range(len(w) - 1))
            cells = split_row(l, len(t['columns']))
            wide = gaps[-(len(t['columns']) - 1):] if gaps else []
            one_word_cells = len(w) == len(t['columns'])           # every word a cell: no gap to judge
            if (not cells or l['page'] != t['page'] or l['column'] != run[0]['column'] or
                    (not one_word_cells and min(wide or [0]) < 3 * gaps[len(gaps) // 2])):
                report['errors'].append({'error': f'{where}: {l["text"]!r} is not a row of it'})
                rows = None
                break
            rows.append(cells)
        if rows is None:
            continue
        cols = t['columns']
        block = {'type': 'table', 'title': t.get('title', ''), 'columns': cols, 'rows': rows,
                 'data': table_data(cols, rows, report, where, t.get('roll_column'))}
        report['tables_to_confirm'].append({'entry': where, 'region': 'text', 'page': t['page'],
                                            'title': block['title'], 'columns': len(cols), 'rows': len(rows)})
        lines = lines[:i] + [merge_lines(run, block)] + lines[i + len(run):]
    return lines


def column_tables(lines, regions, tables_plan, report):
    """A box whose table has no rules, set in columns ("from_columns": 2): its lines below the
    title, read column by column, are the table's columns, a line to a cell, the first line of each
    being its header. The box becomes a table region and those lines its table lines. Columns of
    different lengths are an error."""
    for bid, t in tables_plan.items():
        if not t.get('from_columns'):
            continue
        body = [l for l in lines if l.get('box') == bid and not l.get('heading') and not l.get('table')]
        cols = {}
        for l in body:
            cols.setdefault(l['column'], []).append(plain(l['text']))
        if bid not in regions or len(cols) != t['from_columns'] or len({len(c) for c in cols.values()}) != 1:
            report['errors'].append({'error': f'box {bid}: not {t["from_columns"]} columns of equal length: '
                                     f'{ {k: len(v) for k, v in cols.items()} }'})
            continue
        grid = list(zip(*cols.values()))
        regions[bid] = dict(regions[bid], kind='table', columns=list(grid[0]), rows=[list(r) for r in grid[1:]])
        for l in body:
            l['table'] = True


def convert(layout, plan, taken=()):
    report = {'errors': [], 'questions': [], 'left_out': [], 'tables_to_confirm': [], 'diagrams': [], 'sizes': {}}
    regions = {r['id']: dict(r) for r in layout.get('regions', [])}
    merged = set()
    for bid, t in plan.get('tables', {}).items():       # a table continued in another box
        for cont in t.get('continued_in', []):
            if cont in regions and regions[cont].get('kind') == 'table' and bid in regions:
                regions[bid]['rows'] = regions[bid]['rows'] + regions[cont]['rows']
                merged.add(cont)
            else:
                plan.setdefault('_missing', []).append(cont)
    lines = [dict(l) for l in layout['lines'] if not l['furniture']]
    body = layout.get('body_size', 0)
    orn = [l for l in lines if l['size'] < body and not re.search(r'[^\W_]', l['text']) and
           not re.match(r'^\s*[•●▪]', l['text'])]
    if orn:                                           # flourishes: no letter or digit, below body size
        report['ornaments'] = [{'page': l['page'], 'text': l['text']} for l in orn]
        report['left_out'] += [l['text'] for l in orn]
        lines = [l for l in lines if l not in orn]
    lines = boxes_as_text(lines, plan.get('boxes', {}), report, layout.get('gutters', {}))
    vocab = vocabulary(lines)
    for nh in plan.get('not_headings', []):           # large lines that are body text
        hit = [l for l in lines if l['page'] == nh['page'] and l.get('heading') and
               norm(plain(l['text'])) == norm(nh['text'])]
        if not hit:
            report['errors'].append({'error': f'not_headings: no heading {nh["text"]!r} on page {nh["page"]}'})
        for l in hit:
            l['heading'] = None
    for spec in plan['entries']:                      # body-size lines that are subheadings
        for sub in spec.get('subheadings', []):
            hit = [l for l in lines if l['page'] >= spec['page'] and not l.get('heading') and
                   not l.get('box') and norm(plain(l['text'])) == norm(sub)]
            if not hit:
                report['errors'].append({'error': f'{spec["name"]}: no subheading line {sub!r} '
                                         f'from page {spec["page"]}'})
            if hit:
                hit[0]['heading'] = SUBHEADING
    lines = text_tables(lines, plan.get('text_tables', []), report)
    column_tables(lines, regions, plan.get('tables', {}), report)
    boxes_plan = plan.get('boxes', {})
    tables_plan = plan.get('tables', {})
    for cont in plan.pop('_missing', []):
        report['errors'].append({'error': f'the plan continues a table in {cont}, which was not read as a table'})
    for bid in list(boxes_plan) + list(tables_plan):
        if bid not in regions:
            report['errors'].append({'error': f'the plan names box {bid}, which pdf_layout.py did not find'})

    planned = list(plan['entries'])
    runs = heading_runs(lines)
    intro = plan.get('intro')
    # Walk the lines, cutting entries at planned headings.
    entries = []          # {"spec", "level", "lines": [...], "boxes": [ids]}
    current, pending = None, list(planned)
    seen_boxes = set()
    pending_boxes = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.get('box'):
            bid = l['box']
            if bid not in seen_boxes and bid in merged:
                seen_boxes.add(bid)                       # its rows are in the table it continues
            elif bid not in seen_boxes:
                seen_boxes.add(bid)
                bp = boxes_plan.get(bid, {})
                target = ('to', bp['to']) if 'to' in bp else ('auto', current)
                if 'diagram' in bp:
                    report['diagrams'].append({'box': bid, 'page': l['page'], 'note': bp['diagram']})
                    report['left_out'] += [x['text'] for x in lines if x.get('box') == bid]
                elif 'entry' in bp:
                    e = {'spec': dict(bp['entry'], page=l['page']), 'level': None, 'lines': [], 'boxes': [bid],
                         'own_box': True}
                    entries.append(e)
                else:
                    pending_boxes.append((bid, target))
            i += 1
            continue
        start = next((p for p in pending if p.get('starts_at') and p['page'] == l['page'] and
                      norm(plain(l['text'])).startswith(norm(p['starts_at']))), None)
        if start:
            pending.remove(start)
            current = {'spec': start, 'level': 1, 'size': 99, 'lines': [], 'boxes': []}
            entries.append(current)
        elif i in runs:
            text, last = runs[i]
            match = next((p for p in pending if p['page'] == l['page'] and
                          norm(p.get('heading', p['name'])) == norm(text)), None)
            if match:
                pending.remove(match)
                current = {'spec': match, 'level': l['heading'], 'size': l['size'], 'lines': [], 'boxes': []}
                entries.append(current)
                i = last + 1
                continue
            if current is not None and l['size'] >= current['size']:
                report['errors'].append({'error': f'heading {text!r} on page {l["page"]} is at the level of '
                                         f'{current["spec"]["name"]!r} but the plan doesn\'t place it'})
        if current is None and intro and not (i in runs and l['heading'] == 1):
            current = {'spec': dict(intro, page=l['page']), 'level': 1, 'size': 99, 'lines': [], 'boxes': []}
            entries.append(current)
        if current is None:
            report['left_out'].append(l['text'])
        else:
            current['lines'].append(l)
        i += 1
    for p in pending:
        what = f'line starting {p["starts_at"]!r}' if p.get('starts_at') else f'heading {p["name"]!r}'
        report['errors'].append({'error': f'no {what} on page {p["page"]}'})

    # A box goes to the entry whose text runs just above it on its page, in the columns it spans;
    # with no text above it there, to the entry running into the page. The plan's "to" overrides.
    owner = {id(x): e for e in entries for x in e['lines']}
    report['box_placement'] = []
    expanded = []
    for bid, target in pending_boxes:          # "to" can name several entries: one copy in each
        if target[0] == 'to' and isinstance(target[1], list):
            expanded += [(bid, ('to', name)) for name in target[1]]
        else:
            expanded.append((bid, target))
    for bid, target in expanded:
        if target[0] == 'to':
            name = target[1]
            target = next((e for e in entries if norm(e['spec']['name']) == norm(name)), None)
            if target is None:
                report['errors'].append({'error': f'box {bid}: the plan sends it to {name!r}, an entry '
                                         'that does not exist'})
                continue
        elif isinstance(target, tuple):
            region = regions.get(bid, {})
            x0, top, x1, _ = region.get('bbox', (0, 0, 0, 0))
            page = region.get('page')
            body = [x for x in lines if not x.get('box') and id(x) in owner]
            above = [x for x in body if x['page'] == page and x['baseline'] < top and x['x1'] > x0 and x['x0'] < x1]
            if above:
                target = owner[id(max(above, key=lambda x: x['baseline']))]
            else:
                before = [x for x in body if x['page'] < page]
                target = owner[id(before[-1])] if before else target[1]
        if target is None:
            report['left_out'] += [x['text'] for x in lines if x.get('box') == bid]
            report['questions'].append({'entry': None, 'kind': 'box-before-first-entry',
                                        'text': f'box {bid} left out'})
            continue
        target['boxes'].append(bid)
        title = box_parts([x for x in lines if x.get('box') == bid])[0]
        report['box_placement'].append({'box': bid, 'title': title, 'entry': target['spec']['name']})

    out, records = [], []
    used_slugs = set()
    found_items, describers = [], []
    for e in entries:
        spec = e['spec']
        name = spec['name']
        content = blocks_from_lines(e['lines'], report, name, vocab, e['level'])
        # Subheadings take consecutive levels below the entry's own, whatever sizes the book used.
        ranks = sorted({b['level'] for b in content if b['type'] == 'heading'})
        for b in content:
            if b['type'] == 'heading':
                b['level'] = (e['level'] or 1) + 1 + ranks.index(b['level'])
        for bid in e['boxes']:
            bl = [x for x in lines if x.get('box') == bid]
            title, body, tlines = box_parts(bl)
            region = regions.get(bid, {})
            inner = blocks_from_lines(body, report, name, vocab)
            plan_t = tables_plan.get(bid) or {}
            if region.get('kind') == 'table' and plan_t.get('items'):
                # A price table: one trapping per row; its footnotes go to the items they mark.
                where = f'{name}: table {bid}'
                cols, rows, _, _, _ = table_cells(region, title, plan_t, report, where)
                report['left_out'].append(' '.join(region.get('columns') or []))  # the header: field names
                notes, rest = items.footnotes(body)
                inner = blocks_from_lines(rest, report, name, vocab) if rest else []
                for it in items.item_rows(cols, rows, plan_t['items'], notes, report, where):
                    found_items.append(dict(it, region=bid, page=region['page'], section=name))
                if not inner:
                    if title:
                        report['left_out'].append(title)      # the price table's title
                    continue
            elif region.get('kind') == 'table':
                inner.append(table_block(region, title, plan_t, report, name))
            if e.get('own_box'):
                if title and norm(title) != norm(name):
                    inner.insert(0, {'type': 'heading', 'level': 2, 'text': title})
                elif title:
                    report['left_out'].append(title)      # the entry's own name, as its heading
                content += inner
            else:
                content.append({'type': 'sidebar', 'title': title, 'content': inner})
        if spec.get('headings_as_rows'):
            content = headings_to_rows(content, spec['headings_as_rows'], report, name)
        split = []
        if spec.get('split_headings'):
            content, split = split_at_headings(content, e['lines'], spec, report, name)
        if spec.get('stat_blocks') and not spec.get('category'):
            report['errors'].append({'error': f'{name}: stat_blocks needs a category (creatures)'})
        if spec.get('describes_items'):
            describers.append((name, content))
        cat = spec.get('category', 'rules')
        fields = {'kind': spec.get('kind', 'procedure')} if cat == 'rules' else \
            ({'kind': spec['kind']} if spec.get('kind') else {})
        if spec.get('stat_blocks'):
            content, prof = creatures.stat_blocks(content, report, name)
            fields.update(prof)
        text = '\n'.join(b['text'] for b in content if b['type'] == 'paragraph')
        for lab in spec.get('field_labels', []):
            # The text after a bold label ("**Contraction:** ..."), up to the next bold label or the
            # paragraph's end, gives the field.
            pat = re.compile(r'\*{2,3}' + re.escape(lab) + r':?\*{2,3}:?\s*(.*?)(?=\s*\*{2,3}[A-Z][^*\n]{0,40}:\*{2,3}|\s*\*{2,3}[A-Z][^*\n]{0,40}\*{2,3}:|\n|$)', re.S)
            hit = pat.search(text)
            if hit and plain(hit.group(1)):
                fields[slugify(lab).replace('-', '_')] = plain(hit.group(1))
            else:
                report['errors'].append({'error': f'{name}: no {lab!r} line'})
        if spec.get('field_labels'):
            content = labelled_to_fields(content, spec['field_labels'])
        slug = spec.get('slug') or slugify(name)
        if slug in taken or (cat, slug) in used_slugs:
            slug = f'{slug}-{plan["source"].lower()}'
        used_slugs.add((cat, slug))
        entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': spec.get('heading', name), 'page': spec['page'], 'level': e['level'] or 1,
                 'fields': fields, 'content': content}
        if cat == 'rules':
            entry['kind'] = spec.get('kind', 'procedure')
        if spec.get('aliases'):
            entry['aliases'] = spec['aliases']
        if spec.get('audience'):
            entry['audience'] = spec['audience']
        if spec.get('heading') and norm(spec['heading']) != norm(name):
            report['left_out'].append(spec['heading'])     # printed as the heading of the entry it names
        rel = plan.get('relations', {}).get(f'{cat}/{slug}') or plan.get('relations', {}).get(slug)
        if rel:
            entry['relations'] = rel
        out.append((cat, entry))
        rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': spec['page'], '_category': cat}
        rec.update(fields)
        if spec.get('aliases'):
            rec['aliases'] = spec['aliases']
        if spec.get('audience'):
            rec['audience'] = spec['audience']
        if rel:
            rec['relations'] = rel
        records.append(rec)
        for sub in split:
            add_entry(sub, out, records, plan, taken, used_slugs)

    describe_items(found_items, describers, plan, report)
    for it in found_items:
        add_entry({'name': it['name'], 'category': 'trappings', 'page': it['page'], 'section': it['section'],
                   'fields': it['fields'], 'content': it.get('content', [])}, out, records, plan, taken, used_slugs)
    if found_items:
        report['items'] = len(found_items)

    for bid, t in tables_plan.items():
        if not t.get('slug'):
            continue
        region = regions.get(bid)
        if not region or region.get('kind') != 'table':
            report['errors'].append({'error': f'the plan lists {bid} as a table, but it was not read as one'})
            continue
        title = box_parts([x for x in lines if x.get('box') == bid])[0]
        block = table_block(region, title, t, {'tables_to_confirm': []}, t['title'])   # reported with its entry
        host = next((n for n, en in ((en['name'], en) for _, en in out) if any(
            b.get('type') == 'sidebar' and b['content'] and b['content'][-1] is not None and
            b['content'][-1].get('type') == 'table' and b['content'][-1]['title'] == block['title']
            for b in en['content'])), None)
        entry = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': host or t['title'], 'page': region['page'], 'level': 1,
                 'fields': {'about': t.get('about', ''), 'roll': t.get('roll')}, 'content': [block]}
        rec = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': region['page'], 'about': t.get('about', ''),
               'roll': t.get('roll'), '_category': 'tables'}
        rel = t.get('relations') or plan.get('relations', {}).get(f'tables/{t["slug"]}')
        if rel:
            entry['relations'] = rec['relations'] = rel
        out.append(('tables', entry))
        records.append(rec)
    return out, records, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('layout')
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--taken', action='append', default=[],
                    help='CATEGORY=_index.json of entries already in the library (repeatable)')
    a = ap.parse_args(argv)
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    with open(a.plan, encoding='utf-8') as f:
        plan = json.load(f)
    taken = set()
    for t in a.taken:
        cat, _, path = t.partition('=')
        if cat == 'rules':
            with open(path, encoding='utf-8') as f:
                taken |= {r['slug'] for r in json.load(f) if r.get('source') != plan['source']}
    entries, records, report = convert(layout, plan, taken)
    return write_outputs(entries, records, report, a.out)


def write_outputs(entries, records, report, out):
    """Write each entry's .json and .md (rules entries by slug, others as <category>--<slug>),
    `_records.json` and `_report.json`; print the counts. Returns the exit status."""
    os.makedirs(out, exist_ok=True)
    for cat, e in entries:
        for ext, text in (('json', json.dumps(e, ensure_ascii=False, indent=1) + '\n'), ('md', render(e))):
            name = f'{e["slug"]}.{ext}' if cat == 'rules' else f'{cat}--{e["slug"]}.{ext}'
            with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
                f.write(text)
            report['sizes'][name] = len(text.encode('utf-8'))
    with open(os.path.join(out, '_records.json'), 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n]\n')
    with open(os.path.join(out, '_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    counts = ', '.join(f'{sum(1 for c, _ in entries if c == k)} {k}' for k in sorted({c for c, _ in entries}))
    print(f'{counts}; {len(report["errors"])} errors, {len(report["questions"])} questions, '
          f'{len(report["tables_to_confirm"])} tables to confirm -> {out}', file=sys.stderr)
    return 1 if report['errors'] else 0

if __name__ == '__main__':
    sys.exit(main())
