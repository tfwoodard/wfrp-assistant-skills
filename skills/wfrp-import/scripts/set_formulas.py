#!/usr/bin/env python3
"""Put formulas on a library entry, or take them off (ADR 0005).

A formula is what an entry's rule does to a character's number (an effect), or what it requires or
limits (a check), written for the character builder to evaluate. Its only home is the entry in the
library: nothing about it is kept in a chapter's plan. A re-import carries it over from the entry
it replaces (the converters' --formulas-from); if one is ever lost it is simply written again.

    set_formulas.py ENTRY.json --effects '[{"on": "WP", "add": 5, "at": 1}]'
    set_formulas.py ENTRY.json --checks '[{"id": "one-lore", "read": "One lore unless ...", "at": 0}]'
    set_formulas.py TABLE.json --row "Salt Dreams" --effects '[{"on": "WP", "add": 10}]'
    set_formulas.py RULE.json --grants '[{"id": "skills", "how": "species", "kind": "skill", "from": "species",
                                          "picks": [{"count": 3, "advances": 5}], "at": 1}]'
    set_formulas.py SPELL.json --summary "Heals Intelligence Bonus + Willpower Bonus Wounds."
    set_formulas.py ENTRY.json --effects '[]'           # an empty list takes that kind off

A summary is one line in Claude's own words of what the entry does, for the printed sheet (a spell's
effect under its name, so the book is rarely needed). Never the book's sentences. Say who makes
every Test it names ("if you pass", "if the target passes"). A bonus named in full ("Willpower
Bonus") is printed as the character's own number. --summary "" takes it off.
    set_formulas.py ENTRY.json --show

ENTRY.json is the entry's file in a local copy of the library (library-data/<category>/<slug>.json);
its .md beside it is rewritten to match. Upload both, and check their sizes, as after any import.
"at" is the number (from 0) of the block of the entry that says so; a table's row is named by the
whole text of one of its cells, which must name one row, and needs no "at". Only a formula the
Librarian has confirmed beside its sentence goes in: the text stays the authority.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import formula_problem, norm  # noqa: E402
from render_entry import render  # noqa: E402


def set_formulas(entry, effects=None, checks=None, row=None, grants=None):
    """Change `entry` in place; returns what changed as text. Raises ValueError for a formula that
    doesn't fit the entry."""
    f = entry.setdefault('fields', {})
    said = []
    for kind, items in (('effects', effects), ('checks', checks), ('grants', grants)):
        if items is None:
            continue
        if row is None:
            bad = formula_problem(entry, kind, items) if items else None
            if bad: raise ValueError(bad)
            if items: f[kind] = items
            else: f.pop(kind, None)
            said.append(f'{kind}: {len(items)}' if items else f'{kind}: none')
        elif kind == 'grants':
            raise ValueError('a table row takes "effects" and "checks"')
        else:
            rows = {k: dict(v) for k, v in f.get('rows', {}).items()}
            printed = [str(c) for b in entry.get('content', []) if b.get('type') == 'table'
                       for r in b.get('rows', []) for c in r if norm(str(c)) == norm(row)]
            key = next((k for k in rows if norm(k) == norm(row)), printed[0] if printed else row)   # as the table prints it
            if items: rows.setdefault(key, {})[kind] = items
            else: rows.get(key, {}).pop(kind, None)
            rows = {k: v for k, v in rows.items() if v}
            bad = formula_problem(entry, 'rows', rows) if rows else None
            if bad: raise ValueError(bad)
            if rows: f['rows'] = rows
            else: f.pop('rows', None)
            said.append(f'row "{key}" {kind}: {len(items)}' if items else f'row "{key}" {kind}: none')
    return ', '.join(said)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('entry')
    ap.add_argument('--effects', help='JSON list')
    ap.add_argument('--checks', help='JSON list')
    ap.add_argument('--grants', help='JSON list: what a creation rule gives (ADR 0007)')
    ap.add_argument('--summary', help="one line in your own words of what the entry does, for the printed sheet")
    ap.add_argument('--row', help="the table row the formulas are for, by a cell's whole text")
    ap.add_argument('--show', action='store_true', help="print the entry's formulas and its numbered blocks")
    a = ap.parse_args()
    with open(a.entry, encoding='utf-8') as fh:
        entry = json.load(fh)
    if a.show:
        print(json.dumps({k: v for k, v in entry.get('fields', {}).items() if k in ('effects', 'checks', 'grants', 'rows', 'summary')}, ensure_ascii=False, indent=1))
        for i, b in enumerate(entry.get('content', [])):
            print(f'{i}: {b.get("type")} {(b.get("text") or b.get("title") or "")[:70]}')
        return 0
    if a.effects is None and a.checks is None and a.grants is None and a.summary is None:
        ap.error('give --effects, --checks, --grants, --summary or --show')
    if a.summary is not None:
        if a.row: ap.error('a summary is for the whole entry, not a row')
        if '\n' in a.summary or len(a.summary) > 240: ap.error('a summary is one line, at most 240 characters')
        if a.summary.strip(): entry.setdefault('fields', {})['summary'] = a.summary.strip()
        else: entry.get('fields', {}).pop('summary', None)
    try:
        said = ('summary: ' + ('set' if a.summary.strip() else 'none')) if a.summary is not None and \
            a.effects is None and a.checks is None and a.grants is None else None
        said = said or set_formulas(entry, json.loads(a.effects) if a.effects is not None else None,
                            json.loads(a.checks) if a.checks is not None else None, a.row,
                            json.loads(a.grants) if a.grants is not None else None)
    except ValueError as x:
        print(f'{a.entry}: {x}', file=sys.stderr)
        return 1
    for path, text in ((a.entry, json.dumps(entry, ensure_ascii=False, indent=1) + '\n'),
                       (os.path.splitext(a.entry)[0] + '.md', render(entry))):
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        print(f'{path}: {len(text.encode("utf-8"))} bytes')
    print(said)
    return 0


if __name__ == '__main__':
    sys.exit(main())
