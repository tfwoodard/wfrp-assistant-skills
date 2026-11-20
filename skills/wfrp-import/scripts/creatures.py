"""Creature profiles from an entry's content, for convert_rules.py's "stat_blocks" entries.

A profile is printed as a header row of characteristic names ("M WS BS S T I Ag Dex Int WP
Fel W", read as a heading), a row of values ("4 35 - 55 ..."; "-" for none), and bold-labelled
lists: "Traits:" and "Optional:", their items split at commas outside brackets ("Trained (Broken,
Entertain, War)" is one). An entry with two or more profiles names each by the short line
printed above its header (a named individual: "Gruk – Troll Chieftain").

A profile printed in a box of its own (box_profile(), for a box the plan marks "profile") opens
with its name, sometimes a second line (a career and status), then the header and values, then
bold-labelled runs: the lists (Traits, Optional, Skills, Talents, Trappings, Marks), the spells
("Spells:", alone or with groups under it: "Petty:", "Arcane Spells:", "Lore of Lamps:"), and
any other labelled paragraph (a note, a special rule), kept under `special`. A line set all in
bold with no colon heads what follows the profile (an item's description): the box's text from
there on is returned to be read as prose.
"""
import re

from entry_text import fix_case, join_lines, plain

HEADER = re.compile(r'^M\s+WS\s+BS\b')
CHARACTERISTICS = {'M', 'WS', 'BS', 'S', 'T', 'I', 'Ag', 'Agi', 'Dex', 'Int', 'WP', 'Fel', 'W'}
LABELS = {'Traits': 'traits', 'Optional': 'optional_traits'}
LABEL = re.compile(r'\*{2,3}(' + '|'.join(LABELS) + r')\*{2,3}:?\s*|\*{2,3}(' + '|'.join(LABELS) + r'):\*{2,3}\s*')
NAME_WORDS = 12
LISTS = {'traits': 'traits', 'optional': 'optional_traits', 'skills': 'skills', 'talents': 'talents',
         'trappings': 'trappings', 'marks': 'marks'}
SPELL_GROUP = re.compile(r'^(Petty|Arcane|Lore of .+|.+ Magic)( Magic)?( Spells)?$')
BOX_FIELDS = ('characteristics', 'traits', 'optional_traits', 'skills', 'talents', 'spells', 'trappings',
              'marks', 'special', 'title', 'profile_name')


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


def box_profile(lines, report, where):
    """A box holding one profile -> (the profile, the box's lines after it). The profile has
    `name`, `title` (a second line above the header, when printed), `characteristics`, a list for
    each of Traits, Optional, Skills, Talents, Trappings and Marks printed, `spells` (a list, or
    {group: list} when grouped), `special` ([{label, text}] for other labelled paragraphs) and
    `lines` ([{label, text}], every labelled run in printed order). No header, or values that
    don't match it, is an error and returns (None, lines)."""
    h = next((i for i, l in enumerate(lines) if HEADER.match(plain(l['text']))), None)
    if h is None or h + 1 >= len(lines):
        report['errors'].append({'error': f'{where}: a profile box with no characteristics header'})
        return None, lines
    # The rest of a wrapped profile, set after another line of the box (beside it, in print):
    # brought up under the first half.
    for j in range(h + 3, len(lines) - 1):
        words = plain(lines[j]['text']).split()
        if words and all(w in CHARACTERISTICS for w in words) and \
                len(plain(lines[j + 1]['text']).split()) == len(words):
            lines = lines[:h + 2] + lines[j:j + 2] + lines[h + 2:j] + lines[j + 2:]
            break
    names = plain(lines[h]['text']).split()
    vals = plain(lines[h + 1]['text']).split()
    if len(vals) != len(names):
        report['errors'].append({'error': f'{where}: {len(names)} characteristics, but the row under them '
                                          f'reads {lines[h + 1]["text"]!r}'})
        return None, lines
    report['left_out'].append(plain(lines[h]['text']))        # the header: kept as the characteristics' keys
    first = h
    # A narrow box wraps the profile: the rest of the header, then the rest of the values.
    while h + 3 < len(lines) and plain(lines[h + 2]['text']).split() and \
            all(w in CHARACTERISTICS for w in plain(lines[h + 2]['text']).split()):
        more, their = plain(lines[h + 2]['text']).split(), plain(lines[h + 3]['text']).split()
        if len(their) != len(more):
            report['errors'].append({'error': f'{where}: {len(more)} characteristics, but the row under them '
                                              f'reads {lines[h + 3]["text"]!r}'})
            return None, lines
        report['left_out'].append(plain(lines[h + 2]['text']))
        names, vals, h = names + more, vals + their, h + 2
    above = [fix_case(plain(l['text'])) for l in lines[:first]]
    prof = {'name': above[0] if above else where}
    if len(above) > 1:
        prof['title'] = ' '.join(above[1:])
    prof['characteristics'] = {n: number(v) for n, v in zip(names, vals)}
    runs, i = [], h + 2                  # [[labels], [line fragments]]
    while i < len(lines):
        l = lines[i]
        first = l['spans'][0]
        lead = first['text'].strip()
        if first['bold'] and lead.endswith(':'):
            rest = ' '.join(sp['text'].strip() for sp in l['spans'][1:]).strip()
            runs.append([[x.strip() for x in lead[:-1].split(':')], [rest] if rest else []])
        elif l['bold'] or not runs:
            break                        # a line all in bold, no colon: a heading for what follows
        else:
            runs[-1][1].append(' '.join(sp['text'].strip() for sp in l['spans']))
        i += 1
    printed, spells, group, kept = [], {}, None, []
    for labels, parts in runs:
        text = join_lines(parts, report, where) if parts else ''
        printed.append({'label': ': '.join(labels), 'text': text})
        for k, lab in enumerate(labels):
            last = k == len(labels) - 1
            if lab.lower() in LISTS and last:
                prof[LISTS[lab.lower()]] = split_list(text)
                kept.append(lab)               # the label: kept as the field's name
                group = None
            elif lab == 'Spells':
                group = ''
                kept.append(lab)
                if last and text:
                    spells[''] = split_list(text)
            elif SPELL_GROUP.match(lab) and (group is not None or len(labels) > 1 or lab.endswith('Spells')) and last:
                spells[lab] = split_list(text)
                kept.append(lab)               # the group: kept as a key
                group = lab
            elif last:
                prof.setdefault('special', []).append({'label': lab, 'text': text})
                group = None
            else:
                report['errors'].append({'error': f'{where}: label {": ".join(labels)!r} in a profile is not read'})
    if spells:
        prof['spells'] = spells[''] if list(spells) == [''] else {k: v for k, v in spells.items() if k}
        if '' in spells and len(spells) > 1:
            prof['spells'][''] = spells['']
    prof['lines'] = printed
    prof['_labels'] = kept       # printed labels the fields hold as keys: profile_fields() credits them
    return prof, lines[i:]


def profile_fields(profiles, entry_name, report):
    """The fields an entry takes from the profile boxes it holds: one profile's own fields (its
    name kept as `profile_name` when it says more than the entry's), or `profiles` for several."""
    def fields(p, named):
        out = {k: v for k, v in p.items() if k in BOX_FIELDS}
        return dict({'name': p['name']}, **out) if named else out
    report['left_out'] += [lab for p in profiles for lab in p['_labels']]
    if len(profiles) > 1:
        return {'profiles': [fields(p, True) for p in profiles]}
    p = profiles[0]
    out = fields(p, False)
    if re.sub(r'\W+', '', p['name']).lower() != re.sub(r'\W+', '', entry_name).lower():
        out['profile_name'] = p['name']
    else:
        report['left_out'].append(p['name'])                 # the entry's own name, printed again
    return out


def profile_block(p):
    """A profile as a content block, for an entry that isn't the creature's own (a ritual's
    construct): its name, title, characteristics and labelled lines as printed."""
    block = {'type': 'profile', 'name': p['name'], 'characteristics': p['characteristics'], 'lines': p['lines']}
    if p.get('title'):
        block['meta'] = p['title']
    return block

