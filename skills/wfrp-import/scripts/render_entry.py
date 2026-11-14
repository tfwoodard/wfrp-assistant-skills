#!/usr/bin/env python3
"""Render a library entry's JSON as Markdown (library-layout.md, §4).

The entry's .json file is the data; the .md beside it is this function's output,
written at import so reading it costs nothing. Skills that hold only the JSON
can call render() themselves: it is a pure function, with no I/O.

    render_entry.py ENTRY.json [...]    print each entry's Markdown
"""
import json
import sys

FRONT = ('slug', 'name', 'source', 'chapter', 'section', 'page', 'kind', 'audience', 'relations', 'aliases')


def yaml_value(v):
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) or v == '' or \
        any(ch in v for ch in ':#[]{},"\'') or v.strip() != v else v


def front(entry):
    lines = ['---']
    keys = [k for k in FRONT if k in entry]
    keys += sorted(k for k in entry.get('fields', {}) if k not in keys)    # a key once, even if in both
    for k in keys:
        v = entry[k] if k in entry else entry['fields'][k]
        lines.append(f'{k}: {yaml_value(v)}')
    return lines + ['---', '']


def cell(s):
    return str(s).replace('|', '\\|')


def md_table(b):
    out = []
    if b.get('title'):
        out += [f'**{b["title"]}**', '']
    for ban in b.get('banners', []):
        out += [f'*{ban["text"].strip()}*', '']
    cols = b['columns']
    out.append('| ' + ' | '.join(cell(c) for c in cols) + ' |')
    out.append('|' + '---|' * len(cols))
    starts = {g['before']: g['text'] for g in b.get('groups', [])}
    for i, r in enumerate(b['rows']):
        if i in starts:
            out.append('| ' + ' | '.join([f'***{cell(starts[i])}***'] + [''] * (len(cols) - 1)) + ' |')
        r = list(r) + [''] * (len(cols) - len(r))
        out.append('| ' + ' | '.join(cell(c) for c in r) + ' |')
    for f in b.get('footnotes', []):
        out += ['', f]
    return out


def md_list(items, ordered, indent=''):
    out = []
    for i, it in enumerate(items, 1):
        mark = f'{i}.' if ordered else '-'
        if isinstance(it, dict):
            out.append(f'{indent}{mark} {it["text"]}')
            out += md_list(it['items'], False, indent + '   ')
        else:
            out.append(f'{indent}{mark} {it}')
    return out


def md_profile(b, base, titled=True):
    """A creature's or NPC's profile: its name, its characteristic line as a table, then its
    labelled lines (Traits, Optional, Skills, Talents, Trappings) as printed."""
    out = [f'{"#" * min(max(b.get("level", base + 1) - base + 1, 2), 6)} {b["name"]}', ''] if titled else []
    if b.get('meta'):
        out += [f'*{b["meta"]}*', '']
    ch = b.get('characteristics') or {}
    if ch:
        names = list(ch)
        out.append('| ' + ' | '.join(names) + ' |')
        out.append('|' + '---|' * len(names))
        out.append('| ' + ' | '.join('—' if ch[n] is None else str(ch[n]) for n in names) + ' |')
        out.append('')
    for l in b.get('lines', []):
        out.append(f'**{l["label"]}:** {l["text"]}  ')
    if b.get('lines'):
        out[-1] = out[-1].rstrip()
        out.append('')
    return out


def md_career_levels(b):
    """A career's advance scheme: one row per career level, then each level's skills, talents
    and trappings as printed."""
    out = ['| Level | Title | Status | Characteristics |', '|---|---|---|---|']
    for i, lv in enumerate(b['levels'], 1):
        out.append(f'| {i} | {cell(lv["title"])} | {cell(lv.get("status", ""))} | '
                   f'{cell(", ".join(lv.get("characteristics", [])))} |')
    out.append('')
    for i, lv in enumerate(b['levels'], 1):
        out += [f'***{lv["title"]}*** ({lv.get("status", "")})', '']
        for k, label in (('skills', 'Skills'), ('talents', 'Talents'), ('trappings', 'Trappings')):
            if lv.get(k):
                v = lv[k] if isinstance(lv[k], str) else ', '.join(lv[k])
                out.append(f'- **{label}:** {v}')
        out.append('')
    return out


def md_blocks(blocks, base=1, title=None):
    """Blocks -> Markdown lines. `base` is the page heading level of the entry's own
    title: a heading one level below it renders as "##". A profile named like
    the entry (`title`) is the entry itself and gets no heading of its own."""
    out = []
    for b in blocks:
        t = b['type']
        if t == 'heading':
            out += [f'{"#" * min(max(b["level"] - base + 1, 2), 6)} {b["text"]}', '']
        elif t == 'paragraph':
            out += [b['text'], '']
        elif t == 'list':
            out += md_list(b['items'], b['ordered']) + ['']
        elif t == 'table':
            out += md_table(b) + ['']
        elif t == 'fields':
            if b.get('title'):
                out += [f'**{b["title"]}**', '']
            out += [f'- **{i["label"]}:** {i["text"]}' for i in b['items']] + ['']
        elif t == 'sidebar':
            body = md_blocks(b['content'], base)
            while body and body[-1] == '':
                body.pop()
            lines = ([f'**{b["title"]}**', ''] if b.get('title') else []) + body
            out += [('> ' + l).rstrip() for l in lines] + ['']
        elif t == 'profile':
            out += md_profile(b, base, b['name'] != title) + ['']
        elif t == 'career_levels':
            out += md_career_levels(b) + ['']
        else:
            raise ValueError(f'unknown block type {t!r}')
    return out


def render(entry):
    """Entry dict -> Markdown text."""
    lines = front(entry) + [f'# {entry["name"]}', ''] + md_blocks(entry['content'], entry.get('level', 1), entry['name'])
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    for p in sys.argv[1:]:
        with open(p, encoding='utf-8') as f:
            sys.stdout.write(render(json.load(f)))
