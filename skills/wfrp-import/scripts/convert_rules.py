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
      "relations": {"tests": [{"role": "adds-to", "to": "rules/tests"}]}
    }

Entries. Each planned entry starts at a heading on its page whose words match
its name (or its "heading", when the book prints more: "Fear (Rating)"), and
runs until the next planned entry's heading. An entry is a rules entry (its
"kind": procedure, condition, psychology, glossary) unless it names another
"category" (diseases, say); "field_labels" read the paragraphs that start with
those bold labels into the entry's fields, and a missing one is an error. Smaller headings
inside it become heading blocks. A heading the plan doesn't place, at the size
of the current entry's own heading or larger, is an error: it would be a
sibling entry nobody decided on. Text before the first planned entry (the
chapter's title page) is left out and listed, unless the plan gives an
"intro" entry ({"name", "kind"}) for it; the chapter's title (its largest
heading) is left out either way.

Boxes (pdf_layout.py --boxes). A box becomes a sidebar, under its own title
(its heading lines), in the entry whose text runs just above it on its page in
the columns it spans; with no text above it there, in the entry running into
the page. The plan
can send it to another entry ("to"), make it an entry of its own ("entry"),
or mark it a diagram ("diagram": a flowchart or picture with words, left out
and listed for transcription by hand). A box read as a ruled table becomes a
table block; a table the plan lists under "tables" is also written as an entry
of its own in tables/ (when it gives a "slug"), with `about` and, when it is a
roll table, its roll column's values as {"min", "max"}. The plan can also give
a table's "title", say its read header is a "banner" printed across the
columns, or that its first row is its "header_row"; "continued_in" lists boxes
on later pages holding the rest of its rows, which join it. A table printed without rules is
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
- `left_out`: everything printed that no entry holds.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402
from entry_text import (blocks_from_lines, fix_case, merge_lines, norm, plain, slugify, split_row,  # noqa: E402
                        table_data, vocabulary)


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


def table_block(region, title, plan_t, report, where):
    cols, rows = list(region.get('columns') or []), [list(r) for r in region['rows']]
    plan_t = plan_t or {}
    banners = []
    if plan_t.get('banner'):          # the header read is a banner printed across the columns
        text = ' '.join(c for c in cols if c.strip())
        start = next((i for i, c in enumerate(cols) if c.strip()), 0)
        banners.append({'text': text, 'start': start, 'span': len(cols) - start})
        cols = []
    if plan_t.get('header_row'):      # the first row read is the header (printed below a rule)
        cols, rows = rows[0], rows[1:]
    width = max([len(cols)] + [len(r) for r in rows])
    if not any(c.strip() for c in cols):
        cols = []
    names = cols if cols else [f'Column {i + 1}' for i in range(width)]
    block = {'type': 'table', 'title': plan_t.get('title') or title, 'columns': cols or [''] * width,
             'rows': rows, 'data': table_data(names, rows, report, where, plan_t.get('roll_column'))}
    if banners:
        block['banners'] = banners
    report['tables_to_confirm'].append({'entry': where, 'region': region['id'], 'page': region['page'],
                                        'title': block['title'], 'columns': len(names), 'rows': len(rows)})
    return block


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
            if (not cells or l['page'] != t['page'] or l['column'] != run[0]['column'] or
                    min(wide or [0]) < 3 * gaps[len(gaps) // 2]):
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
    lines = [l for l in layout['lines'] if not l['furniture']]
    vocab = vocabulary(lines)
    lines = text_tables(lines, plan.get('text_tables', []), report)
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
        if i in runs:
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
        report['errors'].append({'error': f'no heading {p["name"]!r} on page {p["page"]}'})

    # A box goes to the entry whose text runs just above it on its page, in the columns it spans;
    # with no text above it there, to the entry running into the page. The plan's "to" overrides.
    owner = {id(x): e for e in entries for x in e['lines']}
    report['box_placement'] = []
    for bid, target in pending_boxes:
        if target[0] == 'to':
            target = next((e for e in entries if norm(e['spec']['name']) == norm(target[1])), None)
            if target is None:
                report['errors'].append({'error': f'box {bid}: the plan sends it to an entry '
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
            if region.get('kind') == 'table':
                inner.append(table_block(region, title, tables_plan.get(bid), report, name))
            if e.get('own_box'):
                if title and norm(title) != norm(name):
                    inner.insert(0, {'type': 'heading', 'level': 2, 'text': title})
                elif title:
                    report['left_out'].append(title)      # the entry's own name, as its heading
                content += inner
            else:
                content.append({'type': 'sidebar', 'title': title, 'content': inner})
        cat = spec.get('category', 'rules')
        fields = {} if cat != 'rules' else {'kind': spec.get('kind', 'procedure')}
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
        slug = spec.get('slug') or slugify(name)
        if slug in taken or slug in used_slugs:
            slug = f'{slug}-{plan["source"].lower()}'
        used_slugs.add(slug)
        entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': spec.get('heading', name), 'page': spec['page'], 'level': e['level'] or 1,
                 'fields': fields, 'content': content}
        if cat == 'rules':
            entry['kind'] = spec.get('kind', 'procedure')
        if spec.get('aliases'):
            entry['aliases'] = spec['aliases']
        if spec.get('heading') and norm(spec['heading']) != norm(name):
            report['left_out'].append(spec['heading'])     # printed as the heading of the entry it names
        rel = plan.get('relations', {}).get(slug)
        if rel:
            entry['relations'] = rel
        out.append((cat, entry))
        rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': spec['page'], '_category': cat}
        rec.update(fields)
        if spec.get('aliases'):
            rec['aliases'] = spec['aliases']
        if rel:
            rec['relations'] = rel
        records.append(rec)

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
        out.append(('tables', entry))
        records.append({'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
                        'section': entry['section'], 'page': region['page'], 'about': t.get('about', ''),
                        'roll': t.get('roll'), '_category': 'tables'})
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
