"""Creature profiles from an entry's content, for convert_rules.py's "stat_blocks" entries.

A profile is printed as a header row of characteristic names ("M WS BS S T I Ag Dex Int WP
Fel W", read as a heading), a row of values ("4 35 - 55 ..."; "-" for none), and bold-labelled
lists: "Traits:" and "Optional:", their items split at commas outside brackets ("Trained (Broken,
Entertain, War)" is one). An entry with two or more profiles names each by the short line
printed above its header (a named individual: "Gruk – Troll Chieftain").
"""
import re

from entry_text import plain

HEADER = re.compile(r'^M\s+WS\s+BS\b')
LABELS = {'Traits': 'traits', 'Optional': 'optional_traits'}
LABEL = re.compile(r'\*{2,3}(' + '|'.join(LABELS) + r')\*{2,3}:?\s*|\*{2,3}(' + '|'.join(LABELS) + r'):\*{2,3}\s*')
NAME_WORDS = 12


def split_list(text):
    """Comma-separated items, keeping commas inside brackets: "A, B (x, y), C" -> [A, B (x, y), C]."""
    items, depth, cur = [], 0, ''
    for ch in plain(text):
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == ',' and depth == 0:
            items.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return [i.rstrip('.') for i in items if i]


def number(v):
    return None if v in ('-', '–', '—') else int(v) if re.fullmatch(r'\d+', v) else v


def stat_blocks(content, report, where):
    """(content without its profiles, the entry's fields): `characteristics`, `traits` and
    `optional_traits` for one profile; `profiles` ([{name, ...}]) for two or more. A header with
    no values row, or values that don't match it, is an error; so is an unnamed second profile."""
    out, profiles, i = [], [], 0
    while i < len(content):
        b = content[i]
        if not (b['type'] == 'heading' and HEADER.match(plain(b['text']))):
            out.append(b)
            i += 1
            continue
        names = plain(b['text']).split()
        report['left_out'].append(plain(b['text']))   # the header: kept as the characteristics' keys
        nxt = content[i + 1] if i + 1 < len(content) else None
        # The values row, read as text or (printed larger than the body) as a heading.
        vals = plain(nxt['text']).split() if nxt and nxt['type'] in ('paragraph', 'heading') else []
        if len(vals) < len(names):
            report['errors'].append({'error': f'{where}: {len(names)} characteristics, but the row '
                                              f'under them reads {nxt["text"] if nxt else None!r}'})
            out.append(b)
            i += 1
            continue
        prof = {'characteristics': {n: number(v) for n, v in zip(names, vals)}}
        rest = ' '.join(vals[len(names):])
        i += 2
        labelled = rest
        while i < len(content) and content[i]['type'] == 'paragraph' and LABEL.match(content[i]['text']):
            labelled += ' ' + content[i]['text']
            i += 1
        parts = LABEL.split(labelled)
        if plain(parts[0]).strip():
            report['errors'].append({'error': f'{where}: text after the values: {parts[0].strip()!r}'})
        for k in range(1, len(parts) - 2, 3):
            lab = parts[k] or parts[k + 1]
            report['left_out'].append(lab)               # the label: kept as the field's name
            prof[LABELS[lab]] = split_list(parts[k + 2])
        profiles.append(prof)
        prof['_above'] = out[-1] if out and out[-1]['type'] == 'paragraph' else None
    if not profiles:
        report['errors'].append({'error': f'{where}: stat_blocks, but no profile'})
        return content, {}
    if len(profiles) == 1:
        profiles[0].pop('_above')
        return out, profiles[0]
    for p in profiles:
        above = p.pop('_above')
        if not above or len(plain(above['text']).split()) > NAME_WORDS:
            report['errors'].append({'error': f'{where}: a profile with no name line above it'})
            continue
        p['name'] = plain(above['text']).strip()
        out.remove(above)
    return out, {'profiles': [dict({'name': p.get('name')}, **{k: v for k, v in p.items() if k != 'name'})
                              for p in profiles]}
