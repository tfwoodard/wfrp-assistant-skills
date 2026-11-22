#!/usr/bin/env python3
"""The campaign notebook (library-layout.md §10): short notes on NPCs, places, items, factions,
threads and facts that matter now, shown on the sheets while they're current and kept, retired, once
they no longer are.

    notebook.py CAMPAIGN_DIR [--gm] add --kind KIND --name NAME --text TEXT [--from N|history] [--for SLUG]
    notebook.py CAMPAIGN_DIR [--gm] edit ID [--name ...] [--text ...] [--kind ...] [--from ...] [--for SLUG|--party]
    notebook.py CAMPAIGN_DIR [--gm] retire ID [--session N] [--why TEXT]
    notebook.py CAMPAIGN_DIR [--gm] restore ID
    notebook.py CAMPAIGN_DIR [--gm] list [--current | --retired] [--for SLUG] [--kind KIND] [--json]

CAMPAIGN_DIR is the campaign's folder (campaigns/<slug>). The notebook is its `notes.json`; with --gm,
`gm/notes.json`, which only the GM reads and no sheet prints.

A note: {"id", "kind" (npc, place, item, faction, thread or fact), "name", "text" (one line, the
group's words or ours: what to remember), "from" (the session it came from: a number, "history"
for sessions/history.md, or null when not known), "for" (a character's slug when it is only theirs;
null or left out for the whole party), "added" (the date written), and once it no longer matters
"retired": {"session", "date", "why"}}. A retired note stays in the file, in searches and in the
history, and leaves the sheets. Ids are made from the name; two notes can't share one.
"""
import argparse, datetime, json, os, re, sys

KINDS = ("npc", "place", "item", "faction", "thread", "fact")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "note"


def path(campaign_dir, gm=False):
    return os.path.join(campaign_dir, "gm", "notes.json") if gm else os.path.join(campaign_dir, "notes.json")


def load(campaign_dir, gm=False):
    """The notes, oldest first; [] when the campaign has no notebook yet."""
    p = path(campaign_dir, gm)
    if not os.path.exists(p): return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("notes", []) if isinstance(data, dict) else data


def save(campaign_dir, notes, gm=False):
    p = path(campaign_dir, gm)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    text = json.dumps({"notes": notes}, ensure_ascii=False, indent=1) + "\n"
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p, len(text.encode("utf-8"))


def current(notes, character=None):
    """The notes still current for one character's sheet: the party's and that character's own."""
    return [n for n in notes if not n.get("retired") and n.get("for") in (None, "", character)]


def where(value):
    """A note's `from`: a session number, "history", or None."""
    if value in (None, ""): return None
    if str(value).lower() == "history": return "history"
    if str(value).isdigit(): return int(value)
    raise SystemExit(f"--from takes a session number or 'history', not '{value}'")


def find(notes, ref):
    hits = [n for n in notes if n["id"] == ref] or [n for n in notes if slug(n["name"]) == slug(ref)]
    if len(hits) != 1:
        raise SystemExit(f"'{ref}' is {len(hits)} notes; give its id" + (": " + ", ".join(n["id"] for n in hits) if hits else ""))
    return hits[0]


def line(n):
    who = f" [{n['for']}]" if n.get("for") else ""
    came = "" if n.get("from") is None else f" (from {'history' if n['from'] == 'history' else 's' + str(n['from'])})"
    gone = ""
    if n.get("retired"):
        r = n["retired"]
        gone = " — retired" + (f" s{r['session']}" if r.get("session") is not None else "") + (f": {r['why']}" if r.get("why") else "")
    return f"{n['id']}: {n['kind']} {n['name']}{who}{came}: {n['text']}{gone}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign_dir")
    ap.add_argument("--gm", action="store_true", help="the GM's notebook (gm/notes.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("--kind", required=True, choices=KINDS); ad.add_argument("--name", required=True)
    ad.add_argument("--text", required=True); ad.add_argument("--from", dest="src"); ad.add_argument("--for", dest="who")
    ad.add_argument("--date")
    ed = sub.add_parser("edit")
    ed.add_argument("id"); ed.add_argument("--kind", choices=KINDS); ed.add_argument("--name"); ed.add_argument("--text")
    ed.add_argument("--from", dest="src"); g = ed.add_mutually_exclusive_group()
    g.add_argument("--for", dest="who"); g.add_argument("--party", action="store_true", help="the whole party's again")
    rt = sub.add_parser("retire")
    rt.add_argument("id"); rt.add_argument("--session", type=int); rt.add_argument("--why"); rt.add_argument("--date")
    rs = sub.add_parser("restore"); rs.add_argument("id")
    ls = sub.add_parser("list")
    g = ls.add_mutually_exclusive_group(); g.add_argument("--current", action="store_true"); g.add_argument("--retired", action="store_true")
    ls.add_argument("--for", dest="who"); ls.add_argument("--kind", choices=KINDS); ls.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    notes = load(a.campaign_dir, a.gm)
    today = datetime.date.today().isoformat()
    if a.cmd == "list":
        got = current(notes, a.who) if a.current else [n for n in notes if n.get("retired")] if a.retired else \
            [n for n in notes if not a.who or n.get("for") in (None, "", a.who)]
        if a.kind: got = [n for n in got if n["kind"] == a.kind]
        print(json.dumps(got, ensure_ascii=False, indent=1) if a.json else "\n".join(line(n) for n in got) or "no notes")
        return 0
    if a.cmd == "add":
        nid = slug(a.name)
        if any(n["id"] == nid for n in notes):
            raise SystemExit(f"there is a note '{nid}' already: change it with edit, or retire it first and add a new name")
        if "\n" in a.text: raise SystemExit("a note is one line")
        n = {"id": nid, "kind": a.kind, "name": a.name.strip(), "text": a.text.strip(), "from": where(a.src),
             **({"for": a.who} if a.who else {}), "added": a.date or today}
        notes.append(n)
        said = "added " + line(n)
    else:
        n = find(notes, a.id)
        if a.cmd == "edit":
            for k in ("kind", "name", "text"):
                if getattr(a, k) is not None: n[k] = getattr(a, k).strip()
            if a.src is not None: n["from"] = where(a.src)
            if a.who: n["for"] = a.who
            if a.party: n.pop("for", None)
            said = "changed " + line(n)
        elif a.cmd == "retire":
            n["retired"] = {"session": a.session, "date": a.date or today, **({"why": a.why} if a.why else {})}
            said = "retired " + line(n)
        else:
            if not n.pop("retired", None): raise SystemExit(f"{n['id']} isn't retired")
            said = "restored " + line(n)
    p, size = save(a.campaign_dir, notes, a.gm)
    print(said)
    print(f"{p}: {size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
