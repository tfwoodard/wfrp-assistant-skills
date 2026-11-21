#!/usr/bin/env python3
"""Write one purchase or change into a character record, in the record's own format.

    apply.py RECORD --library ROOT --campaign SLUG [--out NEW] [--dry-run] <command> ...

Commands:
  buy --characteristic CODE [--count N]       advances in a characteristic (WS, Int ...)
  buy --skill "NAME" [--count N]              advances in a skill, named as the books print it:
                                              "Charm", "Lore (Reikland)"
  buy --talent "NAME"                         a talent, once: "Hardy", "Arcane Magic (Hysh)"
  buy --spell "NAME" [--lore LORE]            a spell; --lore for an Arcane spell when the
                                              character has more than one lore
        with --session N, --date YYYY-MM-DD, --notes TEXT, and --how xp|free|talent (free: given
        in play, no XP; talent: one of the spells Petty Magic gives when it is taken)
  log TEXT [--session N] [--date YYYY-MM-DD]   appends a changelog entry

A purchase is added to the record's `advances` (the build prices it: never write the price), the
record is built before and after, and what the purchase did is printed: its price by the rules and
the campaign's house rules, XP to spend before and after, the numbers on the sheet that moved, and
every difference or note the purchase brought with it (a talent past its Max, XP the character
doesn't have, a skill outside the career at double price). The purchase is written all the same:
the group decides what a difference means. --dry-run prints the same and writes nothing.

An imported record keeps `xp.spent` by hand (its history isn't known), so the price is added to
it. The record is rewritten in place unless --out is given; nothing else in it changes.
"""
import argparse, copy, datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
from library import Library, cli  # noqa: E402


def save(record, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
        f.write("\n")


def line_for(a, lib):
    """The advances line for a buy command, with the name resolved to its entry."""
    if a.characteristic:
        code = next((c for c in bc.CHARS if c.lower() == a.characteristic.lower()), None) or \
            bc.NAME_CHAR.get(bc.norm(a.characteristic))
        if not code: sys.exit(f"'{a.characteristic}' isn't a characteristic: use one of {', '.join(bc.CHARS)}")
        return {"characteristic": code, "count": a.count}, bc.CHAR_NAME[code]
    if a.spell:
        ref = lib.find("spells", a.spell)
        if not ref:
            near = sorted({r["name"] for _, r in lib.index("spells") if bc.norm(a.spell) in bc.norm(r["name"])})[:8]
            sys.exit(f"'{a.spell}' isn't one entry among the spells in play" + (f": did you mean {', '.join(near)}?" if near else "."))
        return {"ref": lib.current(ref), **({"lore": a.lore} if a.lore else {})}, a.spell
    cat, name = ("skills", a.skill) if a.skill else ("talents", a.talent)
    ref, spec = lib.named(cat, name)
    if not ref:
        near = sorted({r["name"] for _, r in lib.index(cat) if bc.norm(name.split("(")[0]) in bc.norm(r["name"])})[:8]
        sys.exit(f"'{name}' isn't one entry among the {cat} in play" + (f": did you mean {', '.join(near)}?" if near else "."))
    ref = lib.current(ref)
    line = {cat[:-1]: ref, **({"specialisation": spec} if spec else {})}
    if cat == "skills": line["count"] = a.count
    return line, name


def moved(before, after):
    """The sheet numbers a purchase changed, as text."""
    out = []
    for c in bc.CHARS:
        x, y = before["characteristics"][c], after["characteristics"][c]
        if x["current"] != y["current"]:
            out.append(f"{bc.CHAR_NAME[c]} {x['current']} -> {y['current']}" + (f" (bonus {x['bonus']} -> {y['bonus']})" if x["bonus"] != y["bonus"] else ""))
    for what, get in (("Wounds", lambda m: m["wounds"]["max"]), ("Movement", lambda m: m["movement"]["base"]),
                      ("Fate", lambda m: m["fate"]["fate"]), ("Resilience", lambda m: m["resilience"]["resilience"]),
                      ("Corruption threshold", lambda m: m["corruption"]["threshold"]), ("Encumbrance limit", lambda m: m["encumbrance"]["max"])):
        if get(before) != get(after): out.append(f"{what} {get(before)} -> {get(after)}")
    old = {r["name"]: r["total"] for r in before["skills"]["basic"] + before["skills"]["advanced"]}
    for r in after["skills"]["basic"] + after["skills"]["advanced"]:
        if old.get(r["name"]) != r["total"]: out.append(f"{r['name']} {old.get(r['name'], 'new')} -> {r['total']}")
    olds = [x["name"] for x in before["spells"]]
    for x in after["spells"][len(olds):]:
        out.append(f"{x['name']} learned (CN {x['cn']}, {x['range']}, {x['duration']})")
    oldt = {t["name"]: t["times"] for t in before["talents"]}
    for t in after["talents"]:
        if oldt.get(t["name"]) != t["times"]: out.append(f"{t['name']}: taken {t['times']}" + (f" of {t['max']}" if t["max"] is not None else ""))
    return out


def buy(record, lib, a):
    line, name = line_for(a, lib)
    line["how"] = a.how
    for k in ("session", "notes"):
        if getattr(a, k) is not None: line[k] = getattr(a, k)
    before = bc.build(copy.deepcopy(record), lib)
    new = copy.deepcopy(record)
    new.setdefault("spells" if a.spell else "advances", []).append(line)
    trial = bc.build(copy.deepcopy(new), lib)
    if a.how == "talent" and not a.spell: sys.exit("--how talent is for a spell that comes with Petty Magic")
    paid = trial["xp"]["purchases"][-1] if a.how == "xp" and trial["xp"]["purchases"] else {}
    price = paid.get("xp") if a.how == "xp" else 0
    said = [f"{name}" + (f" x{a.count}" if "count" in line and a.count != 1 else "") +
            (": " + ("given in play, no XP" if a.how == "free" else "comes with the talent, no XP" if a.how == "talent" else
                    f"{price} XP" if price is not None else "price not worked out"))]
    if a.how == "xp" and price is not None and (new.get("xp") or {}).get("spent") is not None:
        new["xp"]["spent"] += price                    # an imported record keeps its total by hand
    after = bc.build(copy.deepcopy(new), lib)
    said.append(f"XP to spend: {before['xp']['current']} -> {after['xp']['current']}")
    said += ["  " + x for x in moved(before, after)]
    had = {d["id"] for d in before["differences"] + before["accepted"]}
    for d in after["differences"]:
        if d["id"] not in had: said.append(f"Differs from the rules: {d['text']} `{d['id']}`")
    for d in after["accepted"]:
        if d["id"] not in had: said.append(f"Accepted ({d['why']}): {d['text']}")
    now = {d["id"] for d in after["differences"] + after["accepted"]}
    for d in before["differences"] + before["accepted"]:
        if d["id"] not in now: said.append(f"No longer differs: {d['text'].split('. ')[0]}.")
    said += ["Note: " + n for n in after["notes"] if n not in before["notes"]]
    if line.get("specialisation") and "skill" in line:
        try:
            e = lib.entry(line["skill"])
            known = e.get("fields", {}).get("specialisations") or []
            if known and bc.norm(line["specialisation"]) not in [bc.norm(k) for k in known]:
                said.append(f"Note: '{line['specialisation']}' isn't one of the specialisations {e['name']} lists "
                            f"({', '.join(known)}). Others are allowed: check the spelling.")
        except Exception:
            pass
    cat = "talents" if "talent" in line else None
    if cat:
        try:
            e = lib.entry(line["talent"])
            if not e.get("fields", {}).get("effects") and not e.get("fields", {}).get("checks"):
                said.append(f"Note: {e['name']} carries no formula. Read it {bc.cite(e, bc.chapter_titles(lib))}: if it changes "
                            f"a number, the record needs the effect until the Librarian confirms one for the entry.")
        except Exception:
            pass
    date = a.date or datetime.date.today().isoformat()
    new.setdefault("changelog", []).append({"date": date, **({"session": a.session} if a.session is not None else {}),
                                            "text": said[0] if a.how != "xp" else f"Spent {price} XP on {name}" +
                                            (f" x{a.count}" if "count" in line and a.count != 1 else "")})
    return new, said


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buy")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--characteristic"); g.add_argument("--skill"); g.add_argument("--talent"); g.add_argument("--spell")
    b.add_argument("--lore")
    b.add_argument("--count", type=int, default=1)
    b.add_argument("--how", choices=("xp", "free", "talent"), default="xp")
    for p in (b, sub.add_parser("log")):
        p.add_argument("--session", type=int)
        p.add_argument("--date")
    b.add_argument("--notes")
    sub.choices["log"].add_argument("text")
    a = ap.parse_args()
    with open(a.record, encoding="utf-8") as f:
        record = json.load(f)
    if a.cmd == "log":
        new = copy.deepcopy(record)
        new.setdefault("changelog", []).append({"date": a.date or datetime.date.today().isoformat(),
                                                **({"session": a.session} if a.session is not None else {}), "text": a.text})
        said = [f"Logged: {a.text}"]
    else:
        if a.count < 1: sys.exit("--count must be 1 or more")
        if (a.talent or a.spell) and a.count != 1: sys.exit("a talent or a spell is bought once at a time")
        new, said = buy(record, Library(a.library, a.campaign), a)
    print("\n".join(said))
    if a.dry_run:
        print("(dry run: nothing written)")
    else:
        save(new, a.out or a.record)
        print(f"written: {a.out or a.record}")


if __name__ == "__main__":
    cli(main)
