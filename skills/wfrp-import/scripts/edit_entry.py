#!/usr/bin/env python3
"""Change a library entry's fields or relations, and everything that repeats them.

    edit_entry.py --library ROOT skills/lore-runes --set characteristic=Int --set advanced=true \
                  --relation adds-to:skills/lore [--plan sources/DPG/plans/ch3.json] [--dry-run]

What it changes, and nothing else:
  - library-data/<category>/<slug>.json: `fields` set or unset, `relations` added or removed;
  - library-data/<category>/<slug>.md: rendered again from the .json (render_entry.py);
  - library-data/<category>/_index.json: only that entry's own line, with the index fields of its
    category (layout §3) and its relations; every other line stays byte for byte as it was;
  - with --plan: the chapter plan's entry of that name gets the same `fields`, and its
    `relations` map the same relations, written in the plan's own layout, so a re-import keeps them.

A value is read as JSON when it is one (true, 3, "x", ["a"]), otherwise as text: --set
characteristic=Int. --unset FIELD takes a field off; --no-relation ROLE:TARGET takes a relation off.
Formulas and summaries are not set here: they go through set_formulas.py, which checks them.
Nothing is uploaded; the output lists each file written and its size, for the upload.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402

# the fields each category's index records repeat (shared/library-layout.md §3)
INDEX_FIELDS = {
    "rules": ("kind", "aliases"), "tables": ("about", "roll", "kind"), "species": ("aliases",),
    "careers": ("class", "species", "levels", "first_level", "status", "earning_skill"),
    "skills": ("characteristic", "advanced", "grouped"), "talents": ("max", "max_assumed", "tests"),
    "spells": ("kind", "lore", "cn", "range", "target", "duration", "type", "learning_xp"),
    "trappings": ("kind", "group", "price", "enc", "availability"), "qualities": ("kind",),
    "creatures": ("kind", "species_type", "characteristics", "traits", "title"), "traits": ("rated",),
    "diseases": ("contraction", "incubation", "duration"), "mutations": ("kind",), "lore": ("kind",),
}
FORMULAS = ("effects", "checks", "grants", "rows", "lived_through", "summary", "summaries")
ROLES = ("adds-to", "version-of", "distinct-from", "reprint-of", "replaces")


def value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def dump_like(data, raw):
    """`data` as JSON in the layout `raw` was written in (an indent of 0, 1, 2 or 4, or compact),
    or None when no layout reproduces `raw`."""
    old = json.loads(raw)
    end = "\n" if raw.endswith("\n") else ""
    for kw in ({"indent": 0}, {"indent": 1}, {"indent": 2}, {"indent": 4}, {}):
        if json.dumps(old, ensure_ascii=False, **kw) + end == raw:
            return json.dumps(data, ensure_ascii=False, **kw) + end
    return None


def edit_index_line(raw, slug, change):
    """Rewrite the one line of a one-record-per-line index that holds `slug`."""
    lines, hit = raw.split("\n"), None
    for i, line in enumerate(lines):
        s = line.strip().rstrip(",")
        if not s.startswith("{"):
            continue
        rec = json.loads(s)
        if rec.get("slug") == slug:
            if hit is not None:
                raise SystemExit(f"_index.json has {slug} twice")
            hit = i
            new = change(dict(rec))
            if new == rec:
                return raw, False
            lines[i] = line[:len(line) - len(line.lstrip())] + json.dumps(new, ensure_ascii=False) + \
                ("," if line.rstrip().endswith(",") else "")
    if hit is None:
        raise SystemExit(f"_index.json has no record for {slug} on a line of its own")
    out = "\n".join(lines)
    json.loads(out)
    return out, True


def relation(text):
    role, _, target = text.partition(":")
    if role not in ROLES or "/" not in target:
        raise SystemExit(f"'{text}': write ROLE:category/slug, with a role from {', '.join(ROLES)}")
    return {"role": role, "to": target}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True, help="the library's root folder")
    ap.add_argument("ref", help="category/slug")
    ap.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    ap.add_argument("--unset", action="append", default=[], metavar="FIELD")
    ap.add_argument("--relation", action="append", default=[], metavar="ROLE:TARGET")
    ap.add_argument("--no-relation", action="append", default=[], metavar="ROLE:TARGET")
    ap.add_argument("--plan", help="the chapter plan (library-relative or absolute) to carry the same fields and relations")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cat, _, slug = a.ref.partition("/")
    base = os.path.join(a.library, "library-data", cat)
    path = os.path.join(base, slug + ".json")
    if not os.path.exists(path):
        raise SystemExit(f"{path} isn't there")
    sets = {}
    for s in a.set:
        k, eq, v = s.partition("=")
        if not eq or not k:
            raise SystemExit(f"'{s}': write FIELD=VALUE")
        sets[k] = value(v)
    bad = [k for k in list(sets) + a.unset if k in FORMULAS]
    if bad:
        raise SystemExit(f"{', '.join(bad)}: formulas and summaries go through set_formulas.py")
    add, drop = [relation(r) for r in a.relation], [relation(r) for r in a.no_relation]

    with open(path, encoding="utf-8") as f:
        entry = json.load(f)
    fields = entry.setdefault("fields", {})
    fields.update(sets)
    for k in a.unset:
        fields.pop(k, None)
    rels = [r for r in entry.get("relations", []) if r not in drop]
    rels += [r for r in add if r not in rels]
    if rels: entry["relations"] = rels
    else: entry.pop("relations", None)

    out = {path: json.dumps(entry, ensure_ascii=False, indent=1) + "\n",
           os.path.splitext(path)[0] + ".md": render(entry)}
    keys = INDEX_FIELDS.get(cat, ())
    def index_record(rec):
        for k in keys:
            if k in sets: rec[k] = sets[k]
            if k in a.unset: rec.pop(k, None)
        edition = rec.pop("edition", None)
        if rels: rec["relations"] = rels
        else: rec.pop("relations", None)
        if edition is not None: rec["edition"] = edition                      # it stays last, as written
        return rec
    ipath = os.path.join(base, "_index.json")
    with open(ipath, encoding="utf-8") as f:
        raw = f.read()
    new, changed = edit_index_line(raw, slug, index_record)
    if changed: out[ipath] = new

    if a.plan:
        ppath = a.plan if os.path.isabs(a.plan) else os.path.join(a.library, a.plan)
        with open(ppath, encoding="utf-8") as f:
            praw = f.read()
        plan = json.loads(praw)
        hits = [e for e in plan.get("entries", []) if e.get("name") == entry["name"] and e.get("category", "rules") == cat]
        if len(hits) != 1:
            raise SystemExit(f"{ppath}: {len(hits)} entries named '{entry['name']}' in {cat}; expected one")
        pf = dict(hits[0].get("fields") or {})
        pf.update(sets)
        for k in a.unset: pf.pop(k, None)
        if pf: hits[0]["fields"] = pf
        else: hits[0].pop("fields", None)
        if rels: plan.setdefault("relations", {})[a.ref] = rels
        elif a.ref in plan.get("relations", {}): plan["relations"].pop(a.ref)
        text = dump_like(plan, praw)
        if text is None:
            raise SystemExit(f"{ppath}: its layout can't be kept; edit it by hand")
        if text != praw: out[ppath] = text

    for p, text in out.items():
        if not a.dry_run:
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
        print(f"{'would write' if a.dry_run else 'wrote'} {p}: {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
