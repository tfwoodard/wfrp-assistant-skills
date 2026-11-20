#!/usr/bin/env python3
"""Put the exact library wording of entries into a file to hand to the user, without
the text passing through the conversation.

    excerpt.py REF [REF ...] --library ROOT [--campaign SLUG] [--gm] --out FILE

Each REF is an entry ("talents/hardy") or a part of one by its heading path
("rules/advancing-through-your-career#Skill Advances"). The file gets, for each, a
heading with the entry's name, its citation (layout §5), and its text exactly as the
library holds it: a whole entry is its `.md` file's body, unchanged; a part is that
heading's content. The script prints only what it wrote (file, refs, sizes), never the
text, so the wording reaches the user as a file they open, not as text written into
the chat.

A ref the campaign doesn't use (source not in play, GM-only without --gm, replaced by
another entry in play) is refused with the reason (layout §8).

The master copy is shared/scripts/excerpt.py; scripts/sync-shared.sh copies it into
every skill that gives rule text (layout §5, "Exact wording").
Exit status 1 if any ref was refused or not found; the file holds the others.
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import library  # noqa: E402
from library import Library, RefError, chapter_titles, cite  # noqa: E402


def record(lib, ref):
    """(root, index record) for an entry ref, among everything here, used or not."""
    cat, _, slug = ref.split("#", 1)[0].partition("/")
    return next(((r, rec) for r, rec in lib.records(cat) if rec["slug"] == slug), (None, None))


def body(path):
    """A .md entry file without its front matter."""
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if s.startswith("---\n"):
        end = s.find("\n---\n", 4)
        if end != -1: s = s[end + 5:]
    return s.strip() + "\n"


def excerpt(lib, ref):
    """(markdown, None) for a ref, or (None, why it can't be given)."""
    root, rec = record(lib, ref)
    if rec is None:
        return None, "not in the library"
    cat = ref.split("/", 1)[0]
    why = lib.hidden(cat, rec)
    if why:
        return None, f"not used in this campaign: {why}"
    titles = chapter_titles(lib)
    head = ref.split("#", 1)[1].split("›")[-1].strip() if "#" in ref else rec["name"]
    citation = cite(dict(rec, section=head if "#" in ref else rec.get("section")), titles)
    if "#" in ref:
        try:
            text = lib.text(lib.section(ref)).strip() + "\n"
        except RefError as e:
            return None, str(e)
        title = f'{rec["name"]} › {head}'
    else:
        md = os.path.join(root, cat, rec["slug"] + ".md")
        if not os.path.exists(md):
            raise library.MissingFiles([lib.rel(md)])
        text = body(md)
        text = re.sub(r"\A# [^\n]*\n+", "", text)          # the file's own title; ours replaces it
        title = rec["name"]
    return f"## {title}\n\n*{citation}*\n\n{text}", None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--gm", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lib = Library(a.library, a.campaign, a.gm)
    parts, bad = [], []
    for ref in a.refs:
        md, why = excerpt(lib, ref)
        if md: parts.append((ref, md))
        else: bad.append((ref, why))
    if parts:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("\n\n".join(md for _, md in parts))
        print(f"wrote {a.out}: " + ", ".join(f"{ref} ({len(md)} characters)" for ref, md in parts))
        print("Send this file to the user; don't repeat its text in the reply.")
    for ref, why in bad:
        print(f"{ref}: {why}", file=sys.stderr)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    library.cli(main)
