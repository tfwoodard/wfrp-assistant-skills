#!/usr/bin/env python3
"""Show a chapter's heading levels with examples, and preview the entries a choice of levels makes.

    heading_levels.py LAYOUT.json [--examples N]
        each heading level (1 is the largest: the chapter's title), its size and font, how many
        headings it has outside boxes, and examples with their pages: enough to tell which level
        names the things a reader would look up (talents, places, conditions)
    heading_levels.py LAYOUT.json --levels 2,3 [--plan PLAN.json]
        every heading at those levels, numbered, as the entries "entry_levels": [2, 3] would make
        (the plan's own entries marked, and its not_entries); headings at other levels are listed
        after, in case one of them is an entry too. Ends with the plan lines to write.

This is the planning step's one question for a chapter: which heading levels are its entries? Show
the levels to whoever is importing, in plain words ("the large headings, like ..., or the smaller
ones, like ..."), take their answer, then show the preview and ask which of those are really
sections of the entry above them (they go in "not_entries"). No guessing: books use heading sizes
differently from chapter to chapter.
"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import heading_runs, level_entries  # noqa: E402
from entry_text import fix_case, norm  # noqa: E402


def levels_table(lines, runs, examples):
    by = collections.defaultdict(list)
    boxed = collections.Counter()
    for i, (text, _) in sorted(runs.items()):
        l = lines[i]
        if l.get('box'):
            boxed[l['heading']] += 1
            continue
        by[l['heading']].append((fix_case(text), l['page'], round(l['size'], 1), l.get('font')))
    rows = []
    for lv in sorted(set(by) | set(boxed)):
        hs = by.get(lv, [])
        fonts = collections.Counter(f for *_, f in hs).most_common(2)
        rows.append({'level': lv, 'size': hs[0][2] if hs else None, 'fonts': [f for f, _ in fonts], 'headings': len(hs),
                     'in_boxes': boxed.get(lv, 0), 'examples': [f'{n} (p. {p})' for n, p, *_ in hs[:examples]]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('layout')
    ap.add_argument('--levels', help='comma-separated levels to preview as entries, e.g. 2,3')
    ap.add_argument('--plan', help="the chapter's plan, to mark its own entries and not_entries")
    ap.add_argument('--examples', type=int, default=6)
    a = ap.parse_args(argv)
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    lines = [dict(l) for l in layout['lines'] if not l.get('furniture')]
    runs = heading_runs(lines)
    if not a.levels:
        print("Heading levels (1 is the largest; a chapter's title is usually level 1):\n")
        for r in levels_table(lines, runs, a.examples):
            print(f"Level {r['level']}: {r['headings']} headings" + (f" (+{r['in_boxes']} in boxes)" if r['in_boxes'] else '')
                  + (f", {r['size']} pt {', '.join(r['fonts'])}" if r['size'] else ''))
            for x in r['examples']:
                print(f'    {x}')
        print('\nWhich levels name the things a reader would look up? Preview them with --levels.')
        return 0
    levels = [int(x) for x in a.levels.split(',') if x.strip()]
    plan = {'source': '', 'chapter': '', 'entries': []}
    if a.plan:
        with open(a.plan, encoding='utf-8') as f:
            plan = json.load(f)
    report = {'errors': []}
    trial = dict(plan, entry_levels=levels, entries=plan.get('entries') or [])
    made, skip = level_entries(trial, lines, runs, report)
    own = {(norm(e.get('heading', e['name'])), e['page']) for e in plan.get('entries') or []}
    print(f'Entries from levels {levels}:\n')
    n = 0
    for i, (text, _) in sorted(runs.items()):
        l = lines[i]
        if l['heading'] not in levels or l.get('box'):
            continue
        key = (norm(text), l['page'])
        mark = 'the plan\'s own entry' if key in own else 'not an entry (not_entries)' if key in skip or (key[0], None) in skip else ''
        n += 1
        print(f'{n:3}. {fix_case(text)} (p. {l["page"]})' + (f'  [{mark}]' if mark else ''))
    other = [(fix_case(t), lines[i]['page'], lines[i]['heading']) for i, (t, _) in sorted(runs.items())
             if lines[i]['heading'] not in levels and lines[i]['heading'] != 1 and not lines[i].get('box')]
    planned_other = [x for x in other if (norm(x[0]), x[1]) in own]
    if planned_other:
        print('\nThe plan also places these, at other levels:')
        for name, page, lv in planned_other:
            print(f'     {name} (p. {page}, level {lv})')
    for e in report['errors']:
        print('error:', e['error'])
    print('\nPlan lines:\n' + json.dumps({'entry_levels': levels}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
