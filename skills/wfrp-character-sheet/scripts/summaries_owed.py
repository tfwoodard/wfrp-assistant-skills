#!/usr/bin/env python3
"""List the summaries a character's printed sheet still lacks, with each entry's text to write them from.

    summaries_owed.py RECORD --library ROOT --campaign SLUG [--no-text]

The printed sheet (character_pdf.py) gives each talent, spell and condition in play a one-line
summary from its library entry, and prints "No summary yet: read the entry." where there is none.
This lists them:

  - each talent the character has whose entry has no summary, or has summaries for some
    specialisations (`summaries`) but not for the one this character took;
  - each spell the character knows whose entry has no summary;
  - each condition in play (common to the table, on every sheet) whose entry has no summary.

For each it gives the entry's file, its citation, the set_formulas.py command to set the summary
once the Librarian approves it, and the entry's text (unless --no-text). The summaries themselves
are written in your own words and shown to the Librarian beside the text first; this only says what
is owed. Exit status 1 while any is owed.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
import character_pdf  # noqa: E402
from library import Library, cli, norm  # noqa: E402


def entry_file(lib, ref):
    category, slug = ref.split("#", 1)[0].split("/", 1)
    for root, rec in lib.index(category):
        if rec["slug"] == slug:
            return lib.rel(os.path.join(root, category, slug + ".json"))
    return f"{category}/{slug}.json"


def owed(m, lib):
    """[{kind, name, ref, spec, why}] in the sheet's order: talents, spells, conditions."""
    out, seen = [], set()

    def add(kind, name, ref, spec, why):
        if (ref, norm(spec or "")) not in seen:
            seen.add((ref, norm(spec or "")))
            out.append({"kind": kind, "name": name, "ref": ref, "spec": spec, "why": why})

    for t in m.get("talents", []):
        try:
            e = lib.entry(t["ref"])
        except Exception:
            continue
        f = e.get("fields", {})
        spec = t["name"][len(e["name"]) + 2:-1] if t["name"].startswith(e["name"] + " (") else None
        per = f.get("summaries") or {}
        if not f.get("summary") and not per:
            add("talent", e["name"], t["ref"], None, "no summary")
        elif per and spec and not any(norm(k) == norm(spec) for k in per):
            add("talent", t["name"], t["ref"], spec,
                f"summaries for {', '.join(sorted(per))}, none for {spec}")
        elif per and not spec and not f.get("summary"):
            add("talent", e["name"], t["ref"], None, f"summaries only for {', '.join(sorted(per))}")
    for s in m.get("spells", []):
        if not s.get("summary"):
            add("spell", s["name"], s["ref"], None, "no summary")
    for c in character_pdf.conditions_in_play(lib):
        if not c.get("summary"):
            add("condition", c["name"], c["ref"], None, "no summary")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--no-text", action="store_true", help="leave out each entry's text")
    a = ap.parse_args(argv)
    with open(a.record, encoding="utf-8") as f:
        rec = json.load(f)
    lib = Library(a.library, a.campaign)
    m = bc.build(rec, lib)
    items = owed(m, lib)
    who = m.get("name") or m.get("slug") or "the character"
    if not items:
        print(f"Every talent, spell and condition on {who}'s sheet has its summary.")
        return 0
    counts = ", ".join(f"{k}s {n}" for k, n in
                       ((k, sum(1 for i in items if i["kind"] == k)) for k in ("talent", "spell", "condition")) if n)
    print(f"{len(items)} summaries to write for {who}'s sheet ({counts}). Write each in your own words, show it to the "
          "Librarian beside the entry's text, and set it once approved.")
    titles = bc.chapter_titles(lib)
    for i in items:
        e = lib.entry(i["ref"])
        path = entry_file(lib, i["ref"])
        print(f"\n## {i['name']} ({i['kind']}: {i['why']})")
        print(f"{path} {bc.cite(e, titles)}")
        spec = f' --specialisation "{i["spec"]}"' if i["spec"] else ""
        print(f'set: python3 <wfrp-import>/scripts/set_formulas.py "<library>/{path}"{spec} --summary "..."')
        if not a.no_text:
            text = lib.text(e.get("content", [])).strip()
            print("\n" + ("\n".join("> " + line if line else ">" for line in text.splitlines()) if text else "> (no text)"))
    return 1


if __name__ == "__main__":
    cli(lambda: sys.exit(main()))
