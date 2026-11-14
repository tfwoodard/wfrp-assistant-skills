#!/usr/bin/env python3
"""Convert a chapter of spells or prayers (blessings, miracles) into spells and rules entries.

    pdf_layout.py BOOK.pdf --pages 229-257 --boxes --out LAYOUT.json
    convert_spells.py LAYOUT.json --plan PLAN.json --out OUT_DIR [--taken <spells/_index.json>]

PLAN.json (kept in Drive beside the source, never in the repo) is a convert_rules.py plan (its
"entries" are the chapter's rules sections; "intro", "boxes", "tables", "text_tables" and
"relations" work the same) plus the lists the spells sit in:

    {
      "source": "CRB", "chapter": "ch8",
      "lists": [
        {"name": "Keeper Spells", "page": 240, "kind": "petty"},
        {"name": "The Lore of Lamps", "page": 245, "kind": "lore", "lore": "Lamps"},
        {"name": "Miracles of the Keeper", "page": 222, "kind": "miracle", "lore": "the Keeper",
         "entry": false}
      ],
      "entries": [...]
    }

Each list starts at its heading (on its page) and runs to the next list's heading or a heading
as large as its own. The list's heading is itself a rules entry holding the text before its
first spell (its "kind" there is "glossary"), unless it says "entry": false, when its words are
left out and listed. The spells are found, not listed: in a list, every heading at the level of
the first one followed by a field line (CN, Range, Target or Duration) is a spell, and one at that
level without field lines is an error.

A spell's fields: `kind` and `lore` from its list (`lore` may be null), and `cn`, `range`,
`target`, `duration` from its field lines, which stay in the content as a fields block. A spell
without Range, Target or Duration is an error; a "petty", "arcane" or "lore" spell without CN
too. A field line runs on to the next line when that line starts in lower case or has an
unclosed bracket (`field_lines_joined` in the report); "Targets:" is read as `target`
(`labels_as_printed`).

Writes the same files as convert_rules.py: spells--<slug>.json/.md, <slug>.json/.md for rules
entries, `_records.json` (with `_category`) and `_report.json`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import convert, heading_runs, write_outputs  # noqa: E402
from entry_text import label_of, norm, plain, slugify, top_fields  # noqa: E402

LABELS = {'cn': 'cn', 'range': 'range', 'target': 'target', 'targets': 'target', 'duration': 'duration'}
NEEDS_CN = ('petty', 'arcane', 'lore')


def list_spans(lines, runs, plan, report):
    """Each list's heading line and the index its list ends at."""
    starts = []
    for lst in plan.get('lists', []):
        i = next((i for i, (t, _) in sorted(runs.items()) if lines[i]['page'] == lst['page'] and
                  norm(plain(t)) == norm(lst.get('heading', lst['name']))), None)
        if i is None:
            report['errors'].append({'error': f'no list heading {lst["name"]!r} on page {lst["page"]}'})
            continue
        starts.append((i, lst))
    starts.sort(key=lambda x: x[0])
    spans = []
    for n, (i, lst) in enumerate(starts):
        nxt = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        own = lines[i]['heading']
        bigger = next((j for j in sorted(runs) if i < j < nxt and lines[j]['heading'] <= own and
                       not lines[j].get('box')), nxt)
        spans.append((i, runs[i][1], bigger, lst))
    return spans


def find_spells(lines, runs, spans, report):
    """[(heading index, last heading line, spec, fields from the list)] for every spell."""
    found = []
    for i, last_head, end, lst in spans:
        cand = [(j, runs[j]) for j in sorted(runs) if last_head < j < end and not lines[j].get('box')]

        def has_fields(last):
            nxt = lines[last + 1] if last + 1 < len(lines) else None
            return bool(nxt and (label_of(nxt) or '').lower() in LABELS)

        first = next((j for j, (t, last) in cand if has_fields(last)), None)
        if first is None:
            report['errors'].append({'error': f'list {lst["name"]!r}: no spell found'})
            continue
        level = lines[first]['heading']
        for j, (text, last) in cand:
            if lines[j]['heading'] != level:
                continue
            if not has_fields(last):
                report['errors'].append({'error': f'heading {text!r} on page {lines[j]["page"]} is at the level of '
                                         f'the spells in {lst["name"]!r} but has no CN/Range/Target/Duration lines'})
                continue
            spec = {'name': plain(text), 'page': lines[j]['page'], 'category': 'spells'}
            found.append((j, last, spec, {'kind': lst['kind'], 'lore': lst.get('lore')}))
    return found


def convert_chapter(layout, plan, taken=()):
    report = {'errors': []}
    lines = [l for l in layout['lines'] if not l['furniture']]
    runs = heading_runs(lines)
    spans = list_spans(lines, runs, plan, report)
    found = find_spells(lines, runs, spans, report)
    head_lines = {i: lines[i:last + 1] for i, last, _, _ in spans}   # kept by identity: indexes shift below
    parsed = {}
    # Read each spell's field lines into a fields block, from the last spell up.
    for j, last, spec, fields in sorted(found, key=lambda x: -x[0]):
        n, line, got = top_fields(lines[last + 1:], LABELS, report, spec['name'],
                                  usual=('cn', 'range', 'target', 'duration'))
        lines = lines[:last + 1] + [line] + lines[last + 1 + n:]
        fields = dict(fields, **got)
        missing = [f for f in ('range', 'target', 'duration') + (('cn',) if fields['kind'] in NEEDS_CN else ())
                   if f not in fields]
        if missing:
            report['errors'].append({'error': f'{spec["name"]} (page {spec["page"]}): no {", ".join(missing)}'})
        if fields.get('cn', '').isdigit():
            fields['cn'] = int(fields['cn'])
        parsed[(spec['name'], spec['page'])] = fields

    entries = list(plan.get('entries', []))
    left_heads = []
    for i, last, _, lst in spans:
        if lst.get('entry', True):
            entries.append({'name': lst['name'], 'heading': lst.get('heading', lst['name']), 'page': lst['page'],
                            'kind': 'glossary', 'slug': lst.get('slug', slugify(lst['name']))})
        else:
            left_heads += [id(l) for l in head_lines[i]]
    left_out = [l['text'] for l in lines if id(l) in left_heads]
    lines = [l for l in lines if id(l) not in left_heads]
    entries += [s for _, _, s, _ in sorted(found, key=lambda x: x[0])]
    entries.sort(key=lambda e: e['page'])
    rplan = dict(plan, entries=entries)
    out, records, rep = convert(dict(layout, lines=lines), rplan, set(taken))
    rep['errors'] = report['errors'] + rep['errors']
    for k in ('field_lines_joined', 'labels_as_printed', 'labels_not_bold'):
        rep[k] = report.get(k, [])
    rep['left_out'] = rep.get('left_out', []) + left_out
    by_slug = {(r['_category'], r['slug']): r for r in records}
    for cat, e in out:
        if cat != 'spells':
            continue
        f = parsed[(e['name'], e['page'])]
        e['fields'] = f
        rec = by_slug[('spells', e['slug'])]
        rec.update({k: f.get(k) for k in ('kind', 'lore', 'cn', 'range', 'target', 'duration')})
        rec['section'] = e['section'] = section_of(e, spans, lines)
    return out, records, rep


def section_of(entry, spans, lines):
    """The list a spell sits in: the list with its kind and lore."""
    return next((lst['name'] for _, _, _, lst in spans if lst['kind'] == entry['fields']['kind'] and
                 lst.get('lore') == entry['fields']['lore']), entry.get('section'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('layout')
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--taken', help='spells/_index.json of entries already in the library')
    a = ap.parse_args(argv)
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    with open(a.plan, encoding='utf-8') as f:
        plan = json.load(f)
    taken = set()
    if a.taken:
        with open(a.taken, encoding='utf-8') as f:
            taken = {r['slug'] for r in json.load(f) if r.get('source') != plan['source']}
    entries, records, report = convert_chapter(layout, plan, taken)
    return write_outputs(entries, records, report, a.out)


if __name__ == '__main__':
    sys.exit(main())
