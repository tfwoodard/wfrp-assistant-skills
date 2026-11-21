#!/usr/bin/env python3
"""List the library files a character's build needs, and which aren't in this copy of the library.

    needs.py RECORD --library ROOT --campaign SLUG [--all] [--json]

The sheet tools read the library from a folder. When the library is reached through
the Drive connector (no local folder), that folder is a copy made for the session,
holding only what has been fetched. This says what to fetch, all at once, instead of
one failed build per missing file:

  - with nothing fetched yet: `library.json`, the campaign's `campaign.json`, and
    every category's `_index.json` (the library's and the campaign's; one exists
    only when that category has entries, so fetch those that do);
  - then every entry the build opens: the character's species, careers, skills,
    talents, spells and trappings, and the rule tables the sheet reads.

A missing entry is read as empty so the build can go on and find the rest, which can
hide what that entry would have led to. So after fetching, run it again until it says
everything is here: a few rounds (most files come in the first two), not one per file.

--all lists every file the build read as well. Paths are from the library's root, the same in Drive and in
the folder. Exit status 1 while files are missing.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
from library import CATEGORIES, Library, RefError  # noqa: E402


REF = re.compile(r"(%s)/[a-z0-9][a-z0-9-]*" % "|".join(CATEGORIES))


def record_refs(x):
    """Every library ref written in a record ("spells/dart", "rules/x#Heading")."""
    if isinstance(x, dict):
        for v in x.values(): yield from record_refs(v)
    elif isinstance(x, list):
        for v in x: yield from record_refs(v)
    elif isinstance(x, str):
        m = REF.match(x)
        if m: yield m.group(0)


def needs(record, root, campaign=None, gm=False):
    """{"missing": [...], "optional": [...], "read": [...], "error": text or None}: paths from the root.
    missing: files known to exist (entries an index lists, library.json, campaign.json).
    optional: category indexes that aren't here; one exists in Drive only if that category has entries."""
    missing, optional, read, error = [], [], [], None
    if not os.path.exists(os.path.join(root, "library.json")):
        missing.append("library.json")
    lib = Library(root, campaign, gm, lenient=True)
    for c in CATEGORIES:                      # every index: entries and editions are found through them
        for r in lib.roots:
            p = os.path.join(r, c, "_index.json")
            if os.path.exists(p): continue
            optional.append(lib.rel(p))
    for ref in record_refs(record):           # what the record names outright, even if the build stops early
        try:
            lib.entry(ref)
        except RefError:
            pass
    try:
        bc.Builder(record, lib).build()
    except Exception as e:  # an entry read as empty can break the build; what's missing explains it
        error = f"{type(e).__name__}: {e}"
    for p in lib.missing:
        if p not in missing and p not in optional: missing.append(p)
    return {"missing": missing, "optional": optional, "read": list(lib.read), "error": error}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--gm", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with open(a.record, encoding="utf-8") as f:
        rec = json.load(f)
    n = needs(rec, a.library, a.campaign, a.gm)
    if a.json:
        json.dump(n, sys.stdout, indent=1)
        print()
    else:
        if n["missing"]:
            print(f"Fetch these {len(n['missing'])} files into the library folder, at the same paths, then run this again:")
            for p in n["missing"]: print("  " + p)
        else:
            print(f"Everything this build needs is here ({len(n['read'])} library files).")
        if n["optional"]:
            print("Category indexes not here. Fetch each one that exists in Drive (a category with no entries "
                  "has none), or its entries and edition updates stay invisible:")
            for p in n["optional"]: print("  " + p)
        if a.all:
            print("Read:")
            for p in n["read"]: print("  " + p)
        if n["error"] and not n["missing"]:
            print(f"The build failed for another reason: {n['error']}")
    sys.exit(1 if n["missing"] or (n["error"] and not n["missing"]) else 0)


if __name__ == "__main__":
    main()
