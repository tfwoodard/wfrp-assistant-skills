#!/usr/bin/env python3
"""Rewrite an existing chapter plan to use "entry_levels", only where it converts exactly the same.

    plan_levels.py PLAN.json LAYOUT.json [--library-data DIR] [--write]

From the plan's own entries: an instruction most of them carry (true or 1: "stat_blocks",
"describes_items") becomes one of the plan's "defaults", with false on the others; the heading
levels most of them are printed at become "entry_levels"
(the set that places the most of the plan's entries for the fewest headings it would wrongly
make entries); the headings at those levels the plan doesn't place go in "not_entries"; and an
entry keeps its own line only when it needs more than its name and page (a kind or category other
than the defaults, aliases, fields, a heading printed differently, any other key) or isn't at
those levels. The converter is then run on LAYOUT with the old plan and the new one, and the new
plan is written (in the old one's layout, with --write) only if every entry, index record and the
whole report come out the same, from the converter that reads the plan (convert_spells.py for one
with "lists", convert_skills_talents.py for one with "skills" or "talents", convert_rules.py
otherwise; the report's "entries_from_levels" is new and not compared). Otherwise it says what
differs and writes nothing.
"""
import argparse, collections, copy, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import IDENTITY, apply_defaults, convert, heading_runs  # noqa: E402
from edit_entry import dump_like  # noqa: E402
from entry_text import fix_case, norm  # noqa: E402

NEW_IN_REPORT = ('entries_from_levels',)     # what a plan with entry_levels adds to the report


def converter(plan):
    """The name of the converter that reads this plan and a function (layout, plan, library) running it."""
    if plan.get('lists'):
        import convert_spells
        return 'convert_spells.py', lambda lay, p, lib: convert_spells.convert_chapter(lay, p, (), lib)
    if plan.get('skills') or plan.get('talents'):
        import convert_skills_talents
        return 'convert_skills_talents.py', lambda lay, p, lib: convert_skills_talents.convert_chapter(lay, p, None)
    return 'convert_rules.py', lambda lay, p, lib: convert(lay, p, (), lib)


def outcome(layout, plan, library):
    """Everything the plan's own converter makes of LAYOUT: entries, index records and the whole report
    (but what entry_levels adds to it), as JSON text to compare."""
    _, run = converter(plan)
    entries, records, report = run(copy.deepcopy(layout), apply_defaults(copy.deepcopy(plan)), library)
    report = {k: v for k, v in report.items() if k not in NEW_IN_REPORT}
    dump = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)
    return dump(entries), dump(records), {k: dump(v) for k, v in report.items()}


def rewrite(plan, layout):
    """(new plan or None, what was done)."""
    if plan.get('entry_levels'):
        return None, 'has entry_levels already'
    entries = plan.get('entries') or []
    if not entries:
        return None, 'no entries'
    lines = [dict(l) for l in layout['lines'] if not l.get('furniture')]
    runs = heading_runs(lines)
    heads = [(norm(t), lines[i]['page'], lines[i]['heading'], t) for i, (t, _) in sorted(runs.items()) if not lines[i].get('box')]
    at = {}
    for e in entries:
        k = (norm(e.get('heading', e['name'])), e['page'])
        at[k] = next((h[2] for h in heads if (h[0], h[1]) == k), None)
    found = collections.Counter(v for v in at.values() if v)
    if not found:
        return None, "none of the plan's entries is a heading in the layout"
    best = None
    for k in range(1, len(found) + 1):
        S = {lv for lv, _ in found.most_common(k)}
        hit = sum(1 for v in at.values() if v in S)
        extra = sum(1 for h in heads if h[2] in S) - hit
        if best is None or hit - extra > best[0]:
            best = (hit - extra, S)
    S = best[1]
    defaults = dict(plan.get('defaults') or {})
    # an instruction most entries carry, true or 1 ("stat_blocks", "describes_items"): a default,
    # with false written on the entries without it (the conversion check below says if that's safe)
    counts = collections.Counter(k for e in entries for k, v in e.items() if k not in IDENTITY and v in (True, 1)
                                 and not isinstance(v, (dict, list)))
    flags = {k for k, n in counts.items() if n * 2 > len(entries) and k not in defaults}
    if flags:
        entries = [dict({k: False for k in flags if k not in e}, **e) for e in entries]
        for k in flags:
            defaults[k] = collections.Counter(e[k] for e in entries if e[k] is not False).most_common(1)[0][0]
        entries = [{k: v for k, v in e.items() if not (k in flags and v == defaults[k])} for e in entries]
    placed = set(at)
    not_entries = [{'text': t, 'page': p} for n, p, lv, t in heads if lv in S and (n, p) not in placed]
    keep = []
    for e in entries:
        k = (norm(e.get('heading', e['name'])), e['page'])
        simple = set(e) <= {'name', 'page'} | set(defaults) and all(e.get(d, defaults[d]) == defaults[d] for d in defaults)
        name_as_printed = next((fix_case(h[3]) for h in heads if (h[0], h[1]) == k), None) == e['name']
        if not (at.get(k) in S and simple and name_as_printed and 'heading' not in e):
            keep.append(e)
    if len(keep) + len(not_entries) >= len(entries):
        return None, f'levels {sorted(S)} would save nothing ({len(keep)} entries kept, {len(not_entries)} not_entries)'
    new = {}
    for key, v in plan.items():
        if key == 'defaults' or (key == 'chapter' and flags and 'defaults' not in plan):
            if key == 'chapter': new[key] = v
            new['defaults'] = defaults
        elif key == 'entries':
            new['entry_levels'] = sorted(S)
            if not_entries: new['not_entries'] = not_entries
            new['entries'] = keep
        else:
            new[key] = v
    return new, f'levels {sorted(S)}: {len(entries)} entries -> {len(keep)} kept + {len(not_entries)} not_entries'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan')
    ap.add_argument('layout')
    ap.add_argument('--library-data')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    with open(a.plan, encoding='utf-8') as f:
        raw = f.read()
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    plan = json.loads(raw)
    new, said = rewrite(plan, layout)
    print(f'{a.plan}: {said}')
    if not new:
        return 0
    before, after = outcome(layout, plan, a.library_data), outcome(layout, new, a.library_data)
    diff = [k for k, x, y in (('entries', before[0], after[0]), ('index records', before[1], after[1])) if x != y] + \
        [f'report {k}' for k in sorted(set(before[2]) | set(after[2])) if before[2].get(k) != after[2].get(k)]
    if diff:
        print(f'  not written: the conversion differs in {", ".join(diff)}')
        return 1
    print(f'  converts the same with {converter(plan)[0]}: every entry, index record and the whole report')
    text = dump_like(new, raw) or json.dumps(new, ensure_ascii=False, indent=1) + '\n'
    if len(text) >= len(raw):
        print(f'  not written: the new plan is no shorter ({len(text)} characters, {len(raw)} before)')
        return 0
    if a.write:
        with open(a.plan, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'  wrote {len(text.encode("utf-8"))} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
