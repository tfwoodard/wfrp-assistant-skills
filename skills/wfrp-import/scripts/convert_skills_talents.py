#!/usr/bin/env python3
"""Convert a skills-and-talents chapter into skills, talents and rules entries.

    pdf_layout.py BOOK.pdf --pages 117-147 --boxes --out LAYOUT.json
    convert_skills_talents.py LAYOUT.json --plan PLAN.json --out OUT_DIR \
        [--taken skills=<skills/_index.json> --taken talents=<talents/_index.json> ...]

PLAN.json (kept in Drive beside the source, never in the repo) is a convert_rules.py plan (its
"entries" are the chapter's rules sections; "intro", "boxes", "tables", "text_tables" and
"relations" work the same) plus where the lists are:

    {
      "source": "CRB", "chapter": "ch4",
      "skills": {"pages": [118, 131], "section": "Keeper Skill List"},
      "talents": {"pages": [132, 147], "section": "Keeper Talent List"},
      "entries": [{"name": "Keeper Skills", "page": 117, "kind": "procedure"}, ...],
      "boxes": {"126.1": {"to": "Wick Lore"}}
    }

The skills and talents are found, not listed. On the skill pages, every heading at the level of
the first one that reads "Name (Characteristic) basic|advanced[, grouped]" is a skill entry, and
one at that level that doesn't read so is an error. On the talent pages, every heading at the level
of the first one followed by a "Max:" line is a talent entry, and one at that level without it is
an error. So a heading the book sets at an entry's level is never dropped or merged silently.

- A skill's fields: `characteristic` (as printed: "Int"), `advanced`, `grouped`, and its
  `specialisations` (the "Specialisations:" line, kept in the content as a fields block). A
  grouped skill without the line is a question; a skill that isn't grouped but has one, an error.
- A talent's fields: `max` and `tests` (its "Max:" and "Test(s):" lines, as printed, kept in the
  content as a fields block), and `situation`, the word in brackets after its name ("Lamp Sense
  (Weather)" is the entry "Lamp Sense" with situation "Weather"). A field line runs on to the next
  line when that line starts in lower case or the field has an unclosed bracket; each run-on is
  listed under `field_lines_joined` for checking. A label printed another way ("Maximum:") is
  listed under `labels_as_printed`.

Writes the same files as convert_rules.py: <category>--<slug>.json/.md for skills and talents,
<slug>.json/.md for rules entries, `_records.json` (with `_category`) and `_report.json`.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import convert, heading_runs, write_outputs  # noqa: E402
from entry_text import merge_lines, new_paragraph, plain, split_items  # noqa: E402

CHARACTERISTICS = ('WS', 'BS', 'S', 'T', 'I', 'Ag', 'Dex', 'Int', 'WP', 'Fel')
SKILL_HEADING = re.compile(r'^(?P<name>.+?)\s+\((?P<char>' + '|'.join(CHARACTERISTICS) +
                           r')\)\s+(?P<kind>basic|advanced)(?P<grouped>,\s*grouped)?\s*$', re.I)
TALENT_LABELS = {'max': 'max', 'maximum': 'max', 'test': 'tests', 'tests': 'tests'}
SPECIALISATIONS = ('specialisations', 'specializations', 'specialties')


def label_of(line):
    """The bold label a line starts with ("Max:" -> "Max"), or None."""
    sp = line['spans'][0] if line['spans'] else None
    if sp and sp['bold'] and not sp['italic'] and sp['text'].rstrip().endswith(':'):
        return sp['text'].rstrip()[:-1].strip()
    return None


def field_text(run):
    """The words after the label, across the run's lines."""
    return plain(re.sub(r'^\s*\S[^:]*:\s*', '', ' '.join(x['text'] for x in run), count=1))


def in_pages(l, pages):
    return pages and pages[0] <= l['page'] <= pages[1]


def find_entries(lines, plan, report):
    """The skill and talent headings: [(index of heading line, last index, spec, parsed fields)]."""
    runs = heading_runs(lines)
    found = []
    for cat in ('skills', 'talents'):
        pages = (plan.get(cat) or {}).get('pages')
        if not pages:
            continue
        cand = [(i, runs[i]) for i in sorted(runs) if in_pages(lines[i], pages)]

        def is_entry(i, text, last):
            if cat == 'skills':
                return bool(SKILL_HEADING.match(text))
            nxt = lines[last + 1] if last + 1 < len(lines) else None
            return bool(nxt and (label_of(nxt) or '').lower() in ('max', 'maximum'))

        first = next(((i, t, last) for i, (t, last) in cand if is_entry(i, t, last)), None)
        if first is None:
            report['errors'].append({'error': f'no {cat} heading on pages {pages[0]}-{pages[1]}'})
            continue
        level = lines[first[0]]['heading']
        for i, (text, last) in cand:
            if lines[i]['heading'] != level:
                continue
            if not is_entry(i, text, last):
                what = ('read as "Name (Characteristic) basic|advanced"' if cat == 'skills'
                        else 'have a "Max:" line under it')
                report['errors'].append({'error': f'heading {text!r} on page {lines[i]["page"]} is at the '
                                         f'level of the {cat} but doesn\'t {what}'})
                continue
            fields = {}
            if cat == 'skills':
                m = SKILL_HEADING.match(text)
                name = m.group('name').strip()
                char = next(c for c in CHARACTERISTICS if c.lower() == m.group('char').lower())
                fields = {'characteristic': char, 'advanced': m.group('kind').lower() == 'advanced',
                          'grouped': bool(m.group('grouped'))}
            else:
                m = re.match(r'^(.+?)\s*\(([^()]+)\)\s*$', text)
                name = m.group(1) if m else text
                if m:
                    fields['situation'] = m.group(2)
            spec = {'name': name, 'heading': text, 'page': lines[i]['page'], 'category': cat}
            found.append((i, last, spec, fields))
    return found


def take_fields(lines, start, end, cat, report, name):
    """In an entry's lines [start, end), read its field lines into one fields-block line.
    Returns (new lines for the range, fields)."""
    seg = lines[start:end]
    fields, out, k, at_top = {}, [], 0, True
    while k < len(seg):
        l = seg[k]
        lab = label_of(l)
        key = lab and lab.lower()
        if cat == 'talents' and key in TALENT_LABELS and at_top:
            # Talent field lines sit at the top of the entry, one after another.
            run = [l]
            while k + len(run) < len(seg):
                nxt = seg[k + len(run)]
                text = field_text(run)
                if label_of(nxt) or nxt.get('heading') or nxt.get('box') or nxt.get('block'):
                    break
                if not (re.match(r'^[a-z]', plain(nxt['text'])) or text.count('(') > text.count(')')):
                    break
                run.append(nxt)
                report.setdefault('field_lines_joined', []).append(
                    {'entry': name, 'label': lab, 'text': field_text(run)})
            if lab.lower() not in ('max', 'tests', 'test'):
                report.setdefault('labels_as_printed', []).append({'entry': name, 'label': lab})
            fields[TALENT_LABELS[key]] = field_text(run)
            item = {'label': lab, 'text': field_text(run)}
            if out and out[-1].get('block', {}).get('type') == 'fields':
                prev = out.pop()
                block = dict(prev['block'], items=prev['block']['items'] + [item])
                out.append(merge_lines([prev] + run, block))
            else:
                out.append(merge_lines(run, {'type': 'fields', 'title': '', 'items': [item]}))
            k += len(run)
            continue
        if cat == 'skills' and key in SPECIALISATIONS:
            run = [l]
            while k + len(run) < len(seg):
                nxt = seg[k + len(run)]
                if (label_of(nxt) or nxt.get('heading') or nxt.get('box') or nxt.get('block') or
                        new_paragraph(nxt, run[-1])):
                    break
                run.append(nxt)
            text = field_text(run)
            if key != 'specialisations':
                report.setdefault('labels_as_printed', []).append({'entry': name, 'label': lab})
            fields['specialisations'] = [s.strip().rstrip('.') for s in split_items(text)]
            out.append(merge_lines(run, {'type': 'fields', 'title': '', 'items': [{'label': lab, 'text': text}]}))
            k += len(run)
            continue
        at_top = False
        out.append(l)
        k += 1
    return out, fields


def convert_chapter(layout, plan, taken=None):
    taken = taken or {}
    report = {'errors': []}
    lines = [l for l in layout['lines'] if not l['furniture']]
    found = find_entries(lines, plan, report)
    # Read each entry's field lines, from the last entry up so the indexes stay good.
    starts = sorted(i for i, *_ in found)
    stops = {}
    heads = sorted(set(starts) | {i for i in heading_runs(lines) if lines[i]['heading'] <=
                                  min((lines[s]['heading'] for s in starts), default=99)})
    for i in starts:
        later = [h for h in heads if h > i]
        stops[i] = later[0] if later else len(lines)
    parsed = {}
    for i, last, spec, fields in sorted(found, key=lambda x: -x[0]):
        seg, more = take_fields(lines, last + 1, stops[i], spec['category'], report, spec['name'])
        lines = lines[:last + 1] + seg + lines[stops[i]:]
        fields = dict(fields, **more)
        if spec['category'] == 'talents' and 'max' not in fields:
            report['errors'].append({'error': f'{spec["name"]}: no Max line'})
        if spec['category'] == 'skills':
            if fields['grouped'] and 'specialisations' not in fields:
                report.setdefault('questions', []).append({'entry': spec['name'], 'kind': 'no-specialisations',
                                                           'text': 'a grouped skill with no Specialisations line'})
            if not fields['grouped'] and 'specialisations' in fields:
                report['errors'].append({'error': f'{spec["name"]}: Specialisations, but not grouped'})
        parsed[(spec['category'], spec['name'], spec['page'])] = fields

    rules_plan = dict(plan, entries=list(plan.get('entries', [])) + [s for _, _, s, _ in sorted(found)])
    cats = {s['category'] for _, _, s, _ in found}
    all_taken = set().union(*[set(v) for k, v in taken.items() if k in cats]) if taken else set()
    entries, records, rep = convert(dict(layout, lines=lines), rules_plan, all_taken)
    rep['errors'] = report['errors'] + rep['errors']
    rep['questions'] = report.get('questions', []) + rep['questions']
    for k in ('field_lines_joined', 'labels_as_printed'):
        rep[k] = report.get(k, [])

    index_fields = {'skills': ('characteristic', 'advanced', 'grouped'), 'talents': ('max', 'tests')}
    by_slug = {(r['_category'], r['slug']): r for r in records}
    for cat, e in entries:
        if cat not in index_fields:
            continue
        fields = parsed[(cat, e['name'], e['page'])]
        e['fields'] = fields
        e['section'] = plan[cat].get('section', e['section'])
        rec = by_slug[(cat, e['slug'])]
        rec['section'] = e['section']
        for f in index_fields[cat]:
            if f in fields:
                rec[f] = fields[f]
    return entries, records, rep


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
    taken = {}
    for t in a.taken:
        cat, _, path = t.partition('=')
        with open(path, encoding='utf-8') as f:
            taken.setdefault(cat, set()).update(r['slug'] for r in json.load(f) if r.get('source') != plan['source'])
    entries, records, report = convert_chapter(layout, plan, taken)
    return write_outputs(entries, records, report, a.out)


if __name__ == '__main__':
    sys.exit(main())
