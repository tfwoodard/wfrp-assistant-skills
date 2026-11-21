#!/usr/bin/env python3
"""Find library entries by name for a campaign, with the layout's filters already applied.

    find_entry.py NAME [NAME ...] --library ROOT [--campaign SLUG] [--gm]
                  [--category rules,spells] [--text] [--json]

Searches the category indexes (all of them, or --category) for each NAME: an exact
match on a name or alias first, then names that start with it, then names that
contain it. For each match it prints the ref, kind, the citation (layout §5), the
entry's `.md` path from the library's root, and its relations with what each means
for the answer (use both, use instead, cite either, say which you mean).

Entries the campaign doesn't use are listed apart, each with the rule that removes
it (its source isn't in play, it's for the GM, another version of it is used instead),
so the answer can say so instead of "not found" (layout §8). --gm includes GM-only
entries and the campaign's `gm/` library data: only when the user is that GM.

--text prints each used match's text (it needs the entry's `.json` in the folder).
Reads only `_index.json` files otherwise. Exit status 1 when nothing matches.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import library  # noqa: E402
from library import CATEGORIES, Library, chapter_titles, cite, norm  # noqa: E402

MEANS = {"adds-to": "use both: that entry first, then this one",
         "version-of": "the same thing as that entry, as this source prints it: the campaign's source order says which is used",
         "replaces": "the same thing as that entry, as this source prints it: the campaign's source order says which is used",
         "reprint-of": "the same text: cite the one whose source comes first in play",
         "distinct-from": "a different thing of the same name: say which you mean",
         "updated-by": "an older edition's entry, updated by that one"}


def search(lib, name, categories):
    """([used matches], [unused matches]), best kind of match only: exact, else prefix, else contains."""
    n = norm(name)
    titles = chapter_titles(lib)
    tiers = ([], [], [])
    for cat in categories:
        for root, rec in lib.records(cat):
            names = [norm(rec.get("name"))] + [norm(a) for a in rec.get("aliases", [])]
            tier = 0 if n in names else 1 if any(x.startswith(n) for x in names) else 2 if any(n in x for x in names) else None
            if tier is None: continue
            hit = {"ref": f'{cat}/{rec["slug"]}', "name": rec.get("name"), "kind": rec.get("kind"),
                   "source": rec.get("source"), "edition": rec.get("edition"), "cite": cite(rec, titles),
                   "file": lib.rel(os.path.join(root, cat, rec["slug"] + ".md")),
                   "relations": rec.get("relations", []), "unused": lib.hidden(cat, rec)}
            tiers[tier].append(hit)
    for t in tiers:
        for h in t:                                   # the entries that add to it: needed for the answer
            h["added_by"] = [] if h["unused"] else [
                {"ref": ref, "name": e.get("name"), "cite": cite(e, titles)}
                for ref in lib.added_by(h["ref"]) for e in [_record(lib, ref)] if e]
    hits = next((t for t in tiers if t), [])
    order = list(lib.campaign.get("sources", [])) if lib.campaign else []
    hits.sort(key=lambda h: (order.index(h["source"]) if h["source"] in order else len(order), h["ref"]))
    return [h for h in hits if not h["unused"]], [h for h in hits if h["unused"]]


def _record(lib, ref):
    cat, slug = ref.split("/", 1)
    return next((rec for _, rec in lib.index(cat) if rec["slug"] == slug), None)


def show(h, lib, text):
    kind = f' [{h["kind"]}]' if h.get("kind") else ""
    out = [f'- {h["name"]}{kind}: `{h["ref"]}` {h["cite"]}', f'  file: {h["file"]}']
    for r in h["relations"]:
        out.append(f'  {r["role"]} {r["to"]}: {MEANS.get(r["role"], "")}')
    for a in h.get("added_by", []):
        out.append(f'  added to by `{a["ref"]}` {a["name"]} {a["cite"]}: read it as well')
    if text:
        body = lib.text(lib.entry(h["ref"]).get("content", []))
        out += ["", "  " + body.replace("\n", "\n  "), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--gm", action="store_true")
    ap.add_argument("--category", help="categories to search, comma-separated (default: all)")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    cats = [c.strip() for c in a.category.split(",")] if a.category else list(CATEGORIES)
    bad = [c for c in cats if c not in CATEGORIES]
    if bad: sys.exit(f"not a category: {', '.join(bad)} (categories: {', '.join(CATEGORIES)})")
    lib = Library(a.library, a.campaign, a.gm)
    absent = [p for p in lib.absent_indexes() if p.split("/")[1] in cats]
    results, found = {}, False
    for name in a.names:
        used, unused = search(lib, name, cats)
        results[name] = {"used": used, "unused": unused}
        found = found or bool(used)
    if a.json:
        json.dump({"results": results, "indexes_not_here": absent}, sys.stdout, indent=1, ensure_ascii=False)
        print()
    else:
        for name, r in results.items():
            print(f"## {name}")
            if not r["used"] and not r["unused"]:
                print("No entry by that name. Check the sources' chapter lists (layout §3): the chapter may not be imported.")
            for h in r["used"]: print(show(h, lib, a.text))
            if r["unused"]:
                print("Not used in this campaign:")
                for h in r["unused"]: print(f'- {h["name"]}: `{h["ref"]}` {h["cite"]}: {h["unused"]}')
            print()
        if absent:
            print("Category indexes not in this folder (their entries can't be found until they're fetched): "
                  + ", ".join(absent))
    sys.exit(0 if found else 1)


if __name__ == "__main__":
    library.cli(main)
