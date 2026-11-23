#!/usr/bin/env python3
"""Survey what the chapter plans tell the converters, to see what tooling could find for itself.

    plan_survey.py --library ROOT [--json] [--examples N]

Every item of every plan in `sources/*/plans/*.json` is put in one of three groups:

  facts    what the book says about an entry that the converter didn't read (a field such as
           "stacks": false, a relation, who an entry is for). A detector reading the entry's own
           text could propose many of these: the survey checks the simple signals it knows and counts
           how many items already have one.
  map      which headings are entries, of what kind and category, with what names and aliases,
           which tables and sidebars there are. Partly a chapter-wide default could give it: the
           survey counts entries whose kind or category is their chapter's most common one.
  layout   how one PDF is set: icon fonts, column schemes, headings that aren't headings, stat
           blocks, split headings. True of one printing only: what a shared, text-free plan pack
           keyed to the PDF would carry.

It reports, by group and kind, how many items there are, how many a signal or a chapter default
already accounts for, and what's left, most first: a to-do list for detectors. A plan key it
doesn't know is listed as unclassified, never skipped. The report names entries (it reads the
library); keep it out of the repo.
"""
import argparse, collections, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detectors  # noqa: E402

# plan keys, by group (top-level keys, then keys inside an entry)
TOP = {
    "map": {"entries", "intro", "tables", "lists", "rename", "careers", "talents", "skills", "defaults"},
    "facts": {"relations"},
    "layout": {"icon_fonts", "icon_text", "level_icons", "scheme_columns", "not_headings", "text_tables",
               "shared_labels", "whole_words", "hand_tables", "boxes"},
    "about": {"source", "chapter"},
}
ENTRY = {
    "map": {"name", "page", "kind", "category", "slug", "aliases", "heading", "career", "describes_items",
            "heading_only", "subheadings"},
    "facts": {"fields", "audience", "level_updates"},       # fields: checked against detectors.py
    "layout": {"field_labels", "stat_blocks", "split_headings", "split_labels", "starts_at", "headings_as_rows",
               "row_bands"},
}
# a plan key that sets one thing for the whole chapter (a column scheme, the icon fonts) counts once
PER_PLAN = {"intro", "scheme_columns", "icon_text", "icon_fonts", "level_icons", "whole_words", "defaults"}
def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s()]", "", str(s or "").lower())).strip()


def entry_text(root, category, name, source):
    """The library entry's text for a plan entry, or None when it isn't in this copy of the library."""
    p = os.path.join(root, "library-data", category or "", "_index.json")
    if not category or not os.path.exists(p): return None
    with open(p, encoding="utf-8") as f:
        rows = json.load(f)
    rec = next((r for r in rows if norm(r.get("name")) == norm(name) and r.get("source") == source), None)
    path = rec and os.path.join(root, "library-data", category, rec["slug"] + ".json")
    if not path or not os.path.exists(path): return None
    with open(path, encoding="utf-8") as f:
        e = json.load(f)
    return detectors.plain_text(e.get("content"))


def base_skill(root, name):
    b = detectors.base_name(name)
    p = os.path.join(root, "library-data", "skills", "_index.json")
    if not b or not os.path.exists(p): return None
    with open(p, encoding="utf-8") as f:
        return next((r for r in json.load(f) if norm(r.get("name")) == norm(b)), None)


def survey(root, examples=3):
    count = collections.Counter()                 # (group, kind) -> items
    covered = collections.Counter()               # (group, kind) -> items a signal or default accounts for
    how = collections.defaultdict(collections.Counter)    # (group, kind) -> what accounts for them
    seen = collections.defaultdict(list)          # (group, kind) -> examples not accounted for
    unknown, unread, plans = collections.Counter(), [], 0

    def add(group, kind, ok=None, why="", example=None):
        count[(group, kind)] += 1
        if ok:
            covered[(group, kind)] += 1
            how[(group, kind)][why] += 1
        elif example and len(seen[(group, kind)]) < examples:
            seen[(group, kind)].append(example)

    for path in sorted(glob.glob(os.path.join(root, "sources", "*", "plans", "*.json"))):
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
        plans += 1
        src, where = plan.get("source"), os.path.relpath(path, root).replace(os.sep, "/")
        entries = plan.get("entries") or []
        common = {k: (collections.Counter(e.get(k) for e in entries if e.get(k)).most_common(1) or [(None, 0)])[0][0]
                  for k in ("kind", "category")}
        for key, val in plan.items():
            group = next((g for g, ks in TOP.items() if key in ks), None)
            if group is None:
                unknown[f"{key} (plan)"] += 1
                continue
            if group == "about" or key == "entries": continue
            if key == "relations":
                for ref, rels in (val or {}).items():
                    for r in rels:
                        a, b, role = ref.split("/")[-1], str(r.get("to", "")).split("/")[-1], r.get("role")
                        if role == "adds-to":            # "lore-runes" adds to "lore": the name says so
                            add("facts", "relation adds-to", bool(b) and a.startswith(b + "-"), "the names show it",
                                f"{where}: {ref} -> {r.get('to')}")
                        else:                             # two entries of one name: the pair is found by name,
                            same = bool(b) and (a == b or a.startswith(b + "-") or b.startswith(a + "-"))
                            add("facts", f"relation {role}", same, "the names show the pair (which relation is a question)",
                                f"{where}: {ref} -> {r.get('to')}")
                continue
            items = [val] if key in PER_PLAN or not isinstance(val, (list, dict)) else val
            for k in (items if isinstance(items, dict) else range(len(items))):
                add(group, key, example=f"{where}: {key} {k}")
        for e in entries:
            label = f"{where}: {e.get('name')} (p. {e.get('page')})"
            for key, val in e.items():
                group = next((g for g, ks in ENTRY.items() if key in ks), None)
                if group is None:
                    unknown[f"{key} (entry)"] += 1
                    continue
                if key in ("kind", "category"):
                    add("map", f"entry {key}", val == common[key], "the chapter's most common", label)
                elif key == "fields":
                    text = None
                    for fk, fv in (val or {}).items():
                        if text is None:
                            text = entry_text(root, e.get("category") or "rules", e.get("name"), src)   # no category: a rules entry
                            if text is None: unread.append(label); text = ""
                        cat = e.get("category") or "rules"
                        base = base_skill(root, e.get("name")) if cat == "skills" else None
                        found = text and any(p["field"] == fk and p["value"] == fv for p in detectors.propose(
                            cat, e.get("kind"), e.get("name"), {}, text, base))
                        add("facts", f"field {fk}", bool(found), "a detector reads it from its text", f"{label}: {fk}={fv!r}")
                elif key not in ("name", "page"):
                    add(group, f"entry {key}", example=label)
            add("map", "entry (heading is an entry)", example=label)
    rows = sorted(({"group": g, "kind": k, "items": n, "accounted": covered[(g, k)], "left": n - covered[(g, k)],
                    "by": dict(how[(g, k)]), "examples": seen[(g, k)]} for (g, k), n in count.items()),
                  key=lambda r: (-r["left"], r["group"], r["kind"]))
    return {"plans": plans, "rows": rows, "unclassified": dict(unknown), "entries_not_read": unread}


def report(s):
    L = [f"# What the plans tell the converters ({s['plans']} plans)", ""]
    for g in ("facts", "map", "layout"):
        rows = [r for r in s["rows"] if r["group"] == g]
        n, left = sum(r["items"] for r in rows), sum(r["left"] for r in rows)
        L.append(f"- {g}: {n} items, {n - left} accounted for by a signal or default, {left} left")
    L += ["", "## Left to find, most first", "", "| group | kind | items | accounted for | left |", "|---|---|---|---|---|"]
    L += [f"| {r['group']} | {r['kind']} | {r['items']} | {r['accounted']}" + (f" ({', '.join(f'{k}: {v}' for k, v in r['by'].items())})" if r['by'] else "")
          + f" | {r['left']} |" for r in s["rows"]]
    L += ["", "## Examples of what's left"]
    for r in s["rows"]:
        if r["examples"]:
            L += [f"- {r['group']} / {r['kind']}:"] + [f"  - {x}" for x in r["examples"]]
    if s["unclassified"]:
        L += ["", "## Unclassified plan keys (add them to the survey's groups)"] + [f"- {k}: {v}" for k, v in sorted(s["unclassified"].items())]
    L += ["", "Not measured here: whether a converter could tell which headings are entries without the plan",
          "(the map's largest part). That needs each chapter's layout from its PDF."]
    if s["entries_not_read"]:
        L += ["", f"## Entries not in this copy of the library ({len(s['entries_not_read'])}): their fields counted as not accounted for"]
        L += [f"- {x}" for x in s["entries_not_read"][:20]] + ([f"- … and {len(s['entries_not_read']) - 20} more"] if len(s["entries_not_read"]) > 20 else [])
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--examples", type=int, default=3)
    a = ap.parse_args(argv)
    s = survey(a.library, a.examples)
    sys.stdout.write(json.dumps(s, ensure_ascii=False, indent=1) + "\n" if a.json else report(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
