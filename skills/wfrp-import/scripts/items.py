"""Trappings from a price table: one item per row, for convert_rules.py's "items" table plans.

A price table ("Weapon | Price | Enc | Availability | ...") lists one item a row. Rows whose
first cell is empty and whose other cells hold a word or two in capitals ("BASIC", "BLACKPOWDER
AND" / "ENGINEERING") head the rows below: the item's group. A leading "(2H)" marks a two-handed
weapon. Asterisks after a name, a value or a group point at the table's footnotes ("* Needs ...").
"""
import re
import string

from entry_text import fix_case, norm, plain

TWO_HANDED = re.compile(r'^\(2H\)?\s+|^\(2H\)')
MARKS = re.compile(r'(\*+)$')
INNER_MARKS = re.compile(r'(?<=[\w)])(\*+)(?=\s*,)')      # after one of a list's values: "Reload 4*, Salvo 9"
NONE = {'', '–', '—', '-'}
LIST_FIELDS = {'qualities'}


def split_column(cols, rows, index, words, report, where):
    """Two columns read as one (a folded table's "Availability" and the next half's "Item"): the
    first `words` words of each cell at `index` stay, the rest become a cell of their own. A
    cell with no more words than that is an error."""
    def split(cells, i):
        parts = cells[i].split()
        if len(parts) <= words:
            report['errors'].append({'error': f'{where}: cell {cells[i]!r} has nothing to split off'})
            return list(cells)
        return cells[:i] + [' '.join(parts[:words]), ' '.join(parts[words:])] + cells[i + 1:]
    return split(cols, index), [split(r, index) for r in rows]


def footnotes(lines):
    """{"*": text, "**": text} from the lines printed under a table (a footnote starts with its
    asterisks and runs on until the next), and the lines that aren't footnotes."""
    notes, rest, cur = {}, [], None
    for l in lines:
        t = l['text'].strip()                       # the printed text: plain() drops asterisks
        m = re.match(r'^(\*+)\s*(.+)$', t)
        if m:
            cur = m.group(1)
            notes[cur] = m.group(2).strip()
        elif cur:
            notes[cur] += ' ' + t
        else:
            rest.append(l)
    return notes, rest


def group_row(row):
    """A row naming the group of the rows below: its first cell empty, the text in the others; or
    a band in capitals read into several cells, the first among them ("HERBS" "AND" "DRAUGHTS"),
    or into the first cell alone, with nothing beside it."""
    filled = [c.strip() for c in row if c.strip()]
    if row and not row[0].strip() and filled:
        return ' '.join(filled)
    if len(row) > 2 and filled == [row[0].strip()] and filled[0].isupper() and not any(ch.isdigit() for ch in filled[0]):
        return filled[0]                              # the band set at the left: "BLACKPOWDER" and nothing beside it
    if (len(filled) > 1 and len(filled) < len(row) and all(c.isupper() for c in filled) and
            not any(ch.isdigit() for c in filled for ch in c)):
        return ' '.join(filled)
    return None


def value(key, cell):
    cell = cell.strip()
    if key in LIST_FIELDS:
        return [] if cell in NONE else [c.strip() for c in cell.split(',') if c.strip()]
    return cell


def item_rows(cols, rows, spec, notes, report, where):
    """The items a table lists: [{"name", "fields"}] in printed order. `spec` gives the item
    `kind` and `fields` ({column header: field}); the first column is the name. Each mark that
    points at no footnote, and each footnote nothing points at, is an error; the book's own
    slip, a mark it prints no footnote for, is named in the spec's "marks_without_notes"
    ([item names]): the mark stays on the value as printed and the item is listed under
    `excused`. "listed_again" (["<group>/<name>"]) names a row that repeats an item of an
    earlier group: the first item takes both groups, the row is left out and the report's
    `listed_again` says so. "listed_elsewhere" names a row repeating an item another chapter
    of the book has given already: the row is left out, and `listed_again` says so."""
    fields = spec.get('fields', {})
    loose = {norm(n) for n in spec.get('marks_without_notes', ())}
    again = set(spec.get('listed_again', ()))
    elsewhere = set(spec.get('listed_elsewhere', ()))
    emptied = set()                                   # groups a row was left out of
    missing = [h for h in fields if h not in cols]
    if missing:
        report['errors'].append({'error': f'{where}: no column {", ".join(map(repr, missing))} in {cols}'})
        return []
    items, group, gmarks, used = [], None, '', set()
    for row in rows:
        g = group_row(row)
        if g is not None:
            m = MARKS.search(g)
            gmarks = m.group(1) if m else ''
            group = fix_case(MARKS.sub('', g).strip())
            if group.isupper():                       # too short for fix_case ("TIN")
                group = string.capwords(group.lower())
            continue
        named = MARKS.search(row[0].strip())          # a mark on the name itself (plain() would drop it)
        name = plain(MARKS.sub('', row[0].strip())).strip()
        if f'{group}/{MARKS.sub("", name).strip()}' in again:
            # The same item listed again under another group (a shot two guns take): one item.
            first = next((it for it in items if it['name'] == MARKS.sub('', name).strip()), None)
            if first is None:
                report['errors'].append({'error': f'{where}: "listed_again" names {group}/{name}, but no row '
                                                  'above it has that name'})
            else:
                first['fields']['group'] = f'{first["fields"].get("group", "")}, {group}'.strip(', ')
                report.setdefault('listed_again', []).append({'where': where, 'item': name, 'group': group})
                report['left_out'].append(' '.join(c for c in row if c))
            continue
        if f'{group}/{MARKS.sub("", name).strip()}' in elsewhere:
            # An item another chapter of the book lists, with its description: that entry stands.
            report.setdefault('listed_again', []).append({'where': where, 'item': name, 'group': group,
                                                          'first': 'in another chapter'})
            report['left_out'].append(' '.join(c for c in row if c))
            emptied.add(group)
            continue
        if not name:
            report['errors'].append({'error': f'{where}: a row with no name: {row}'})
            continue
        f = {'kind': spec['kind']}
        if group:
            f['group'] = group
        if TWO_HANDED.match(name):
            name = TWO_HANDED.sub('', name)
            f['two_handed'] = True
            report['left_out'].append('(2H)')        # printed before the name; kept as two_handed
        m = named or MARKS.search(name)
        marks = [x for x in (m.group(1) if m else '', gmarks) if x]
        name = MARKS.sub('', name).strip()
        for header, key in fields.items():
            cell = row[cols.index(header)].strip()
            cm = MARKS.search(cell)
            if cm and cm.group(1) not in notes and norm(name) in loose:
                report.setdefault('excused', []).append(
                    f'{where}: {name!r} is marked {cm.group(1)!r} in {header!r} and the plan says the book '
                    'prints no such footnote: the mark stays on the value')
            elif cm:                                 # a mark after a value ("+SB+6*")
                marks.append(cm.group(1))
                cell = MARKS.sub('', cell).strip()
            if key in LIST_FIELDS:                   # ...or after one of a list's values
                marks += INNER_MARKS.findall(cell)
                cell = INNER_MARKS.sub('', cell)
            f[key] = value(key, cell)
        for mk in marks:
            if mk in notes:
                f.setdefault('notes', []).append(notes[mk])
                used.add(mk)
            else:
                report['errors'].append({'error': f'{where}: {name!r} is marked {mk!r}, but no footnote is'})
        items.append({'name': name, 'fields': f})
    for mk in notes:
        if mk not in used:
            report['errors'].append({'error': f'{where}: footnote {mk!r} marks no item'})
    for g in sorted(emptied - {it['fields'].get('group') for it in items}):
        report['left_out'].append(g)                  # a group whose only rows are listed elsewhere
    return items


def label(text):
    """A paragraph opening with a bold label ("**Coat:** Protects ..."): (label, the rest), else None."""
    m = re.match(r'^\*{2,3}([^*]+?):?\*{2,3}:?\s*(.*)$', text, re.S)
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def base_name(n):
    """An item's name without its quantity or unit: "Fish Hooks (12)" -> "fish hooks",
    "Room, common/night" -> "room, common"."""
    n = re.sub(r'\s*\([^)]*\)', '', norm(n)).split('/')[0]
    return n.strip().rstrip('s')


def same_item(item, label):
    """A description's label names an item: the same name allowing for case, quotes, a plural
    "s" and the item's quantity or unit, or the name before the item's last ", ..." ("Bugman's
    Ale" for "Bugman's Ale, pint")."""
    a, b = base_name(item), base_name(label)
    return a == b or (',' in a and base_name(a.rsplit(',', 1)[0]) == b)
