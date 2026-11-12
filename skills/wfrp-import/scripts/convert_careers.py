#!/usr/bin/env python3
"""Convert career pages (one career per page) into career entries (library-layout.md §4).

    convert_careers.py LAYOUT.json --plan PLAN.json --out OUT_DIR [--taken careers=<careers/_index.json>]

LAYOUT.json comes from pdf_layout.py, run with the plan's icon fonts
(--icon-fonts), so the level icons are listed as marks and shapes rather than
read as text. PLAN.json (kept in Drive beside the source, never in the repo):

    {
      "source": "CRB", "chapter": "ch3",
      "level_icons": {"1": {"mark_font": "IconFont"}, "2": {"pts": 12}, "3": {"pts": 20}, "4": {"pts": 7}},
      "scheme_columns": {"ws": "WS", "bs": "BS", "s": "S", "t": "T", "i": "I",
                         "agi": "Ag", "dex": "Dex", "int": "Int", "wp": "WP", "fel": "Fel"},
      "careers": [{"name": "Lamp Warden", "page": 12, "class": "Burghers"}, ...],
      "relations": {"lamp-warden": [{"role": "adds-to", "to": "careers/lamp-warden"}]}
    }

`level_icons` says how each career level is marked: a glyph in a font (part of
the font's name) or a drawn shape with that many points. `scheme_columns` maps
each advance-scheme header label, lower-cased, to its characteristic code.

Each career page has: its name (a heading), the species who may enter it, its
description, the "<Name> Advance Scheme" box (a header row of characteristics,
an icon under each one a level advances), and "Career Path": four level lines
("Wick Boy — Brass 2", each with its icon) followed by Skills:, Talents: and
Trappings: lines.

For each career it writes <slug>.json (fields and content blocks, with the
four levels as a `career_levels` block) and <slug>.md (render_entry.py), and
for the chapter `_records.json` (index records) and `_report.json`:

- `errors`: anything that doesn't read as expected (a missing scheme or level, a
  level icon that doesn't match its level). Exit status 1 when there are any.
- `questions`: things to settle with the Librarian (a scheme that isn't 3/1/1/1,
  italic items, line-end hyphens joined).
- `left_out`: the printed words the entries don't hold as text (the scheme's
  title and header labels, the "Career Path" heading, and the Skills:, Talents:
  and Trappings: labels the `career_levels` block holds as keys), so check_coverage.py can
  account for every word.

It only reformats what pdf_layout.py read; it never guesses a value.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402

LEVEL_LINE = re.compile(r'^(?P<title>.+?)\s*[—–]\s*(?P<status>(?:Brass|Silver|Gold)\s+\d+)$')
LABELS = ('Skills', 'Talents', 'Trappings')


def slugify(s):
    s = s.lower().replace('’', '').replace("'", '')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('’', "'")).strip().lower()


def marked(line):
    """A line's text with italic and bold spans marked as Markdown."""
    out = []
    for sp in line['spans']:
        m = re.match(r'^(.*?)([,;:.]*)$', sp['text'], re.S)
        t, tail = m.group(1), m.group(2)          # punctuation after a styled run stays outside its marks
        if not t:
            out.append(sp['text'])
            continue
        if sp['italic'] and sp['bold']:
            t = f'***{t}***'
        elif sp['italic']:
            t = f'*{t}*'
        elif sp['bold']:
            t = f'**{t}**'
        out.append(t + tail)
    return ' '.join(out)


def plain(s):
    return re.sub(r'\*+', '', s).strip()


def split_items(s):
    """Split a printed list at commas outside parentheses."""
    items, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            items.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def join_lines(parts, report, where):
    """Join a run of line texts into one string. A line that ends with a hyphen joins the next with
    no space, and each such join is listed as a question."""
    out = ''
    for p in parts:
        end = re.search(r'-(\*{0,3})$', out)
        if not out:
            out = p
        elif end:
            marks = end.group(1)
            if marks and p.startswith(marks) and not p.startswith(marks + '*'):
                out, p = out[:-len(marks)], p[len(marks):]     # one styled run across the line break
            report['questions'].append({'career': where, 'kind': 'hyphen-join', 'text': (out[-20:] + p[:20])})
            out += p
        else:
            out += ' ' + p
    return out


def icon_level(plan_icons, marks, shapes):
    """Which level a group of marks/shapes stands for, or None."""
    for lv, spec in plan_icons.items():
        if 'mark_font' in spec and any(spec['mark_font'].lower() in m['font'].lower() and not m['text'].isspace()
                                       for m in marks):
            return int(lv)
        if 'pts' in spec and shapes and max(s['pts'] for s in shapes) == spec['pts']:
            return int(lv)
    return None


def near(items, top, bottom, x0=None, x1=None):
    return [i for i in items if i['bottom'] >= top and i['top'] <= bottom and
            (x0 is None or i['x1'] >= x0) and (x1 is None or i['x0'] <= x1)]


def read_scheme(career, lines, i, marks, shapes, plan, report):
    """lines[i] is the scheme's title; lines[i+1] its header row. Returns {level: [codes]}."""
    hdr = lines[i + 1] if i + 1 < len(lines) else None
    cols = plan['scheme_columns']
    if not hdr or len(hdr['words']) != len(cols):
        report['errors'].append({'career': career, 'error': 'advance scheme header row not found or the wrong size',
                                 'got': hdr and hdr['text']})
        return None
    labels = []
    for text, x0, x1 in hdr['words']:
        code = cols.get(text.lower())
        if not code:
            report['errors'].append({'career': career, 'error': f'unknown scheme column {text!r}'})
            return None
        labels.append((code, (x0 + x1) / 2))
    bottom = max(l['top'] for l in [hdr]) + hdr['size'] + 2
    band_m = near(marks, bottom, bottom + 22)
    band_s = near(shapes, bottom, bottom + 22)
    width = (labels[-1][1] - labels[0][1]) / (len(labels) - 1)
    levels = {}
    for code, cx in labels:
        ms = [m for m in band_m if abs((m['x0'] + m['x1']) / 2 - cx) < width / 2 and not m['text'].isspace()]
        ss = [s for s in band_s if abs((s['x0'] + s['x1']) / 2 - cx) < width / 2]
        if not ms and not ss:
            continue
        lv = icon_level(plan['level_icons'], ms, ss)
        if lv is None:
            report['errors'].append({'career': career, 'error': f'unrecognised icon under {code}',
                                     'shapes': [s['pts'] for s in ss], 'marks': [m['font'] for m in ms]})
            continue
        levels.setdefault(lv, []).append(code)
    counts = [len(levels.get(n, [])) for n in (1, 2, 3, 4)]
    if counts != [3, 1, 1, 1]:
        report['questions'].append({'career': career, 'kind': 'scheme-counts',
                                    'text': f'characteristics per level {counts}, not [3, 1, 1, 1]'})
    return levels


def read_path(career, lines, start, marks, shapes, plan, report):
    """lines[start] is the "Career Path" heading. Returns the four levels and the index after them."""
    levels, cur, label, buf = [], None, None, []

    def flush():
        nonlocal label, buf
        if cur is not None and label:
            cur['_raw'][label] = join_lines(buf, report, career)
        label, buf = None, []

    i = start + 1
    while i < len(lines) and lines[i]['column'] == lines[start]['column']:
        l = lines[i]
        m = LEVEL_LINE.match(plain(l['text']))
        if m and l['spans'][0]['bold']:
            flush()
            cur = {'title': m.group('title'), 'status': m.group('status'), '_raw': {}}
            lv = icon_level(plan['level_icons'], near(marks, l['top'] - 4, l['top'] + l['size'] + 2, None, l['x0']),
                            near(shapes, l['top'] - 4, l['top'] + l['size'] + 2, None, l['x0']))
            if lv != len(levels) + 1:
                report['errors'].append({'career': career, 'error': f'level {len(levels) + 1} line '
                                         f'{cur["title"]!r} has the icon of level {lv}'})
            levels.append(cur)
        elif cur is not None and l['spans'][0]['bold'] and plain(l['spans'][0]['text']).rstrip(':') in LABELS:
            flush()
            label = plain(l['spans'][0]['text']).rstrip(':')
            report['left_out'].append(l['spans'][0]['text'])
            rest = ' '.join(marked({'spans': [sp]}) for sp in l['spans'][1:])
            buf = [rest] if rest else []
        elif cur is not None and label:
            buf.append(marked(l))
        else:
            break
        i += 1
    flush()
    if len(levels) != 4:
        report['errors'].append({'career': career, 'error': f'{len(levels)} career levels, not 4'})
    return levels, i


def paragraphs(lines, report, career):
    """Description lines -> paragraph blocks: a new paragraph at a column change or a wider gap."""
    blocks, buf, prev = [], [], None
    for l in lines:
        if prev is not None and (l['column'] != prev['column'] or l['page'] != prev['page'] or
                                 l['baseline'] - prev['baseline'] > 1.6 * prev['size'] or
                                 l['baseline'] < prev['baseline']):
            blocks.append({'type': 'paragraph', 'text': join_lines(buf, report, career)})
            buf = []
        buf.append(marked(l))
        prev = l
    if buf:
        blocks.append({'type': 'paragraph', 'text': join_lines(buf, report, career)})
    return blocks


def convert(layout, plan, taken=()):
    report = {'errors': [], 'questions': [], 'left_out': [], 'sizes': {}}
    entries, records = [], []
    marks_by_page, shapes_by_page = {}, {}
    for m in layout.get('marks', []):
        marks_by_page.setdefault(m['page'], []).append(m)
    for s in layout.get('shapes', []):
        shapes_by_page.setdefault(s['page'], []).append(s)
    for c in plan['careers']:
        name, page = c['name'], c['page']
        lines = [l for l in layout['lines'] if l['page'] == page and not l['furniture']]
        marks, shapes = marks_by_page.get(page, []), shapes_by_page.get(page, [])
        ti = next((i for i, l in enumerate(lines) if l.get('heading') and norm(l['text']) == norm(name)), None)
        if ti is None:
            report['errors'].append({'career': name, 'error': f'no heading {name!r} on page {page}'})
            continue
        used = {ti}
        species_line = lines[ti + 1] if ti + 1 < len(lines) and not lines[ti + 1].get('heading') else None
        if species_line is None:
            report['errors'].append({'career': name, 'error': 'no species line after the heading'})
            species = []
        else:
            used.add(ti + 1)
            species = split_items(plain(species_line['text']))
        si = next((i for i, l in enumerate(lines) if norm(l['text']) == norm(name + ' advance scheme')), None)
        scheme = None
        if si is None:
            report['errors'].append({'career': name, 'error': 'no advance scheme'})
        else:
            scheme = read_scheme(name, lines, si, marks, shapes, plan, report)
            used |= {si, si + 1}
            report['left_out'] += [lines[si]['text'], lines[si + 1]['text']]
        pi = next((i for i, l in enumerate(lines) if norm(l['text']) == 'career path'), None)
        levels = []
        if pi is None:
            report['errors'].append({'career': name, 'error': 'no Career Path'})
        else:
            levels, end = read_path(name, lines, pi, marks, shapes, plan, report)
            used |= set(range(pi, end))
            report['left_out'].append(lines[pi]['text'])
        rest = [l for i, l in enumerate(lines) if i not in used]
        content = []
        if species_line is not None:
            content.append({'type': 'paragraph', 'text': marked(species_line)})
        content += paragraphs(rest, report, name)

        lv_blocks, advances, italics = [], {}, []
        for n, lv in enumerate(levels, 1):
            raw = lv.pop('_raw')
            block = {'title': lv['title'], 'status': lv['status'],
                     'characteristics': (scheme or {}).get(n, [])}
            adv = {'status': lv['status'], 'characteristics': block['characteristics']}
            for lab in LABELS:
                if lab not in raw:
                    report['errors'].append({'career': name, 'error': f'level {n} has no {lab}'})
                    continue
                items = split_items(raw[lab])
                if '' in items:
                    report['questions'].append({'career': name, 'kind': 'empty-item',
                                                'text': f'level {n} {lab}: an empty item (two commas in a row '
                                                        'as printed), left out of the list'})
                    items = [x for x in items if x]
                block[lab.lower()] = items
                adv[lab.lower()] = [plain(x) for x in items]
                italics += [plain(x) for x in items if '*' in x]
            lv_blocks.append(block)
            advances[str(n)] = adv
        content.append({'type': 'career_levels', 'levels': lv_blocks})
        if italics:
            report['questions'].append({'career': name, 'kind': 'italic-items', 'text': ', '.join(italics)})

        slug = slugify(name)
        if slug in taken:
            slug = f'{slug}-{plan["source"].lower()}'
        fields = {'class': c.get('class'), 'species': species,
                  'levels': [l['title'] for l in lv_blocks], 'status': [l['status'] for l in lv_blocks],
                  'advances': advances}
        if not c.get('class'):
            report['errors'].append({'career': name, 'error': 'the plan gives no class'})
        entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': name, 'page': page, 'level': 1, 'fields': fields, 'content': content}
        rel = plan.get('relations', {}).get(slug)
        if rel:
            entry['relations'] = rel
        entries.append(entry)
        rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
               'section': name, 'page': page, 'class': fields['class'], 'species': species,
               'levels': fields['levels'], 'status': fields['status']}
        if rel:
            rec['relations'] = rel
        records.append(rec)
    return entries, records, report


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
        if cat == 'careers':
            with open(path, encoding='utf-8') as f:
                taken |= {r['slug'] for r in json.load(f) if r.get('source') != plan['source']}
    entries, records, report = convert(layout, plan, taken)
    os.makedirs(a.out, exist_ok=True)
    for e in entries:
        for ext, text in (('json', json.dumps(e, ensure_ascii=False, indent=1) + '\n'), ('md', render(e))):
            p = os.path.join(a.out, f'{e["slug"]}.{ext}')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text)
            report['sizes'][os.path.basename(p)] = len(text.encode('utf-8'))
    with open(os.path.join(a.out, '_records.json'), 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n]\n')
    with open(os.path.join(a.out, '_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'{len(entries)} careers, {len(report["errors"])} errors, {len(report["questions"])} questions '
          f'-> {a.out}', file=sys.stderr)
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
