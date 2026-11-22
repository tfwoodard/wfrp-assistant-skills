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
    set_formulas.py TALENT.json --specialisation "Magical Prodigy" --summary "Spells cost half the XP."
    set_formulas.py ENTRY.json --effects '[]'           # an empty list takes that kind off

A summary is one line in Claude's own words of what the entry does, for the printed sheet (a spell's
effect under its name, so the book is rarely needed). Never the book's sentences. Say who makes
every Test it names ("if you pass", "if the target passes"). A bonus named in full ("Willpower
Bonus") is printed as the character's own number. --summary "" takes it off. With --specialisation,
the summary is for one specialisation (a talent's chosen benefit): the sheet prints the entry's
summary, which every character gets, then the one for the specialisation the character took.
    set_formulas.py ENTRY.json --show

ENTRY.json is the entry's file in a local copy of the library (library-data/<category>/<slug>.json);
its .md beside it is rewritten to match. Upload both, and check their sizes, as after any import.
"at" is the number (from 0) of the block of the entry that says so; a table's row is named by the
whole text of one of its cells, which must name one row, and needs no "at". Only a formula the
Librarian has confirmed beside its sentence goes in: the text stays the authority.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import entry_tables, formula_problem, norm  # noqa: E402
from render_entry import render  # noqa: E402


def set_formulas(entry, effects=None, checks=None, row=None, grants=None, row_fields=None, lived_through=None):
    """Change `entry` in place; returns what changed as text. Raises ValueError for a formula that
    doesn't fit the entry. `row_fields` ({"careers", "psychology", "burdens"}, with `row`) are the
    rest of what a Time's row gives an Elder; `lived_through` names the table of Times (ADR 0008)."""
    f = entry.setdefault('fields', {})
    said = []
    if lived_through is not None:
        bad = formula_problem(entry, 'lived_through', lived_through) if lived_through else None
        if bad: raise ValueError(bad)
        if lived_through: f['lived_through'] = lived_through
        else: f.pop('lived_through', None)
        said.append('lived_through: ' + ('set' if lived_through else 'none'))
    pairs = [('effects', effects), ('checks', checks), ('grants', grants)]
    if row_fields is not None:
        if row is None: raise ValueError('--row-fields goes with --row')
        if not isinstance(row_fields, dict) or set(row_fields) - {'careers', 'psychology', 'burdens'}:
            raise ValueError('--row-fields takes "careers", "psychology" and "burdens"')
        pairs += list(row_fields.items())
    for kind, items in pairs:
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
            printed = [str(c) for b in entry_tables(entry.get('content'))
                       for r in b.get('rows', []) for c in r if norm(str(c)) == norm(row)]
            key = next((k for k in rows if norm(k) == norm(row)), printed[0] if printed else row)   # as the table prints it
            if items or items == 0 and kind == 'careers': rows.setdefault(key, {})[kind] = items
            else: rows.get(key, {}).pop(kind, None)
            rows = {k: v for k, v in rows.items() if v}
            bad = formula_problem(entry, 'rows', rows) if rows else None
            if bad: raise ValueError(bad)
            if rows: f['rows'] = rows
            else: f.pop('rows', None)
            said.append(f'row "{key}" {kind}: ' + (str(items) if kind == 'careers' else str(len(items)) if items else 'none'))
    return ', '.join(said)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('entry')
    ap.add_argument('--effects', help='JSON list')
    ap.add_argument('--checks', help='JSON list')
    ap.add_argument('--grants', help='JSON list: what a creation rule gives (ADR 0007)')
    ap.add_argument('--summary', help="one line in your own words of what the entry does, for the printed sheet")
    ap.add_argument('--specialisation', help="with --summary: the specialisation the summary is for")
    ap.add_argument('--row', help="the table row the formulas are for, by a cell's whole text")
    ap.add_argument('--row-fields', help='with --row, JSON: what a Time gives an Elder: {"careers": N, "psychology": [...], '
                    '"burdens": [{"text": "...", "only_earliest": true}]} (ADR 0008)')
    ap.add_argument('--lived-through', help='JSON {"table": TITLE, "column": NAME}: the table of Times an Elder lives through '
                    '(ADR 0008); {} removes it')
    ap.add_argument('--show', action='store_true', help="print the entry's formulas and its numbered blocks")
    a = ap.parse_args()
    with open(a.entry, encoding='utf-8') as fh:
        entry = json.load(fh)
    if a.show:
        print(json.dumps({k: v for k, v in entry.get('fields', {}).items() if k in ('effects', 'checks', 'grants', 'rows', 'lived_through', 'summary', 'summaries')}, ensure_ascii=False, indent=1))
        for i, b in enumerate(entry.get('content', [])):
            print(f'{i}: {b.get("type")} {(b.get("text") or b.get("title") or "")[:70]}')
        return 0
    if a.effects is None and a.checks is None and a.grants is None and a.summary is None and a.row_fields is None \
            and a.lived_through is None:
        ap.error('give --effects, --checks, --grants, --row-fields, --lived-through, --summary or --show')
    if a.specialisation and a.summary is None:
        ap.error('--specialisation goes with --summary')
    if a.summary is not None:
        if a.row: ap.error('a summary is for the whole entry, not a row')
        if '\n' in a.summary or len(a.summary) > 320: ap.error('a summary is one line, at most 320 characters')
        f = entry.setdefault('fields', {})
        if a.specialisation:
            per = dict(f.get('summaries') or {})
            if a.summary.strip(): per[a.specialisation.strip()] = a.summary.strip()
            else: per.pop(a.specialisation.strip(), None)
            if per: f['summaries'] = per
            else: f.pop('summaries', None)
        elif a.summary.strip(): f['summary'] = a.summary.strip()
        else: f.pop('summary', None)
    try:
        said = ('summary: ' + ('set' if a.summary.strip() else 'none')) if a.summary is not None and \
            a.effects is None and a.checks is None and a.grants is None and a.row_fields is None and a.lived_through is None else None
        said = said or set_formulas(entry, json.loads(a.effects) if a.effects is not None else None,
                            json.loads(a.checks) if a.checks is not None else None, a.row,
                            json.loads(a.grants) if a.grants is not None else None,
                            json.loads(a.row_fields) if a.row_fields is not None else None,
                            json.loads(a.lived_through) if a.lived_through is not None else None)
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
