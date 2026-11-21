#!/usr/bin/env python3
"""What a character can spend XP on now, with each price worked out from the library.

    options.py RECORD --library ROOT --campaign SLUG [--json]

Reads the record as it is and reports, for the current career and the levels reached in it:

  - XP: earned, spent, to spend;
  - characteristics the career advances: advances taken, the price of the next one;
  - skills the career lists: the same, per skill the character has under each listed name, and the
    listed name itself when it is a choice ("Lore (Any)") or not yet taken;
  - spells: how many the character knows under each talent that teaches them, and the price of the
    next;
  - talents on sale (the current level's, or every level reached where a house rule opens them):
    times taken, the Max as a number, the price, and "at its Max" when it can't be taken again;
  - creation, while there is something left to give: each grant of the creation rules (ADR 0007)
    with what it still gives, what has been taken from it, and the list it gives from; the
    species' talents not yet taken (an "or" is one choice), and random talents left to roll on
    their table;
  - while the record is being created (`creating`, set by apply.py start): the class's and the first
    career level's trappings, each marked as had or to add (with its choices, dice and container),
    and the money the career's status gives;
  - what completing the current level still needs, and the least XP that takes;
  - earlier levels left unfinished.

Prices follow the campaign's house rules where the builder has a setting for them (layout §8,
`set`). Anything outside the career can still be bought at double the price; it isn't listed.
Nothing is written: apply.py writes a purchase.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
from library import Library, cli  # noqa: E402


def spec_of(name):
    m = re.search(r"\((.+)\)$", name)
    return m.group(1) if m else None


def creation(b, m):
    """What the creation grants still give, and where from."""
    sp = b.lists()["species"]
    first = next((f for _, n, f in b.lists()["levels"] if n == 1), {})
    lists = {("species", "skill"): sp.get("skills", []), ("species", "talent"): sp.get("talents", []),
             ("first-career-level", "skill"): first.get("skills", []), ("first-career-level", "talent"): first.get("talents", []),
             ("first-career-level", "characteristic"): [bc.CHAR_NAME.get(c, c) for c in first.get("characteristics", [])]}
    out = []
    for g in m.get("creation", []):
        if g["from"] == "table":
            offer = [f"the {b.lib.entry(b.lib.current(g['table']))['name']} table (roll on it)"]
        else:
            offer = [x if isinstance(x, str) else " or ".join(x.get("choose_one", [])) for x in lists.get((g["from"], g["kind"]), [])
                     if not (isinstance(x, dict) and "random" in x)]
        if not (g["left"] or g["to_take"]): continue
        out.append({k: g[k] for k in ("rule", "id", "cite", "how", "kind", "left", "to_take", "taken")} | {"from": offer})
    return out


def report(record, lib):
    b = bc.Builder(record, lib)
    m = b.build()
    rows = b.cost_rows()
    out = {"name": m.get("name"), "career": {k: m["career"].get(k) for k in ("name", "level", "level_name")},
           "xp": {k: m["xp"][k] for k in ("total", "spent", "current")}, "house_rules": m.get("house_rules", {}),
           "characteristics": [], "skills": [], "talents": [], "notes": []}
    if rows is None:
        out["notes"].append("The cost table isn't in the library, so no price is worked out.")
    cur = (record.get("careers") or [{}])[-1]
    cref = lib.current(cur.get("ref") or "")
    levels = [(c, n, f) for c, n, f in b.lists()["levels"] if c == cref]
    now = levels[-1][1] if levels else None

    def price(kind, already, count=1):
        if rows is None: return None
        steps = [b.step_cost(rows, already + j, kind) for j in range(count)]
        return None if None in steps else sum(steps)

    for _, n, f in levels:
        for c in f.get("characteristics", []):
            if any(x["code"] == c for x in out["characteristics"]): continue
            adv = m["characteristics"].get(c, {}).get("advances", 0)
            out["characteristics"].append({"code": c, "name": bc.CHAR_NAME.get(c, c), "level": n, "advances": adv,
                                           "next": price("characteristic", adv)})
    have = m["skills"]["basic"] + m["skills"]["advanced"]
    slots = [sl for sl in b.skill_slots() if sl["career"] == cref]
    for sl in slots:
        if not sl["ref"]:
            out["notes"].append(f"{sl['listed']}: not found among the library's skills, so it isn't priced. Look it up.")
            continue
        mine = [r for r in have if b.slot_covers(sl, r["ref"], spec_of(r["name"])) and (r["advances"] or sl["kind"] != "open")]
        for r in mine:
            if not any(x["name"] == r["name"] for x in out["skills"]):
                out["skills"].append({"name": r["name"], "listed": sl["listed"], "level": sl["level"], "advances": r["advances"],
                                      "total": r["total"], "next": price("skill", r["advances"]),
                                      **({"chosen_for": sl["listed"]} if sl["kind"] == "one" else {}),
                                      **({"assumed": True} if sl["assumed"] else {})})
        # a name still to be chosen: an open one always (another specialisation can be started), a
        # single choice until it is made, an exact one until it is taken
        if sl["kind"] == "open" or not mine:
            if not any(x["name"] == sl["listed"] for x in out["skills"]):
                out["skills"].append({"name": sl["listed"], "listed": sl["listed"], "level": sl["level"], "advances": 0, "total": None,
                                      "next": price("skill", 0), **({"choose": True} if sl["kind"] != "exact" else {})})
    open_levels = [n for _, n, _ in levels] if b.setting("talents_from") == "levels-reached" else [now]
    taken = {(t["ref"], spec_of(t["name"])): t for t in m["talents"]}
    rising = b.setting("talent_cost") == "rising"
    for _, n, f in levels:
        if n not in open_levels: continue
        for listed in f.get("talents", []):
            lref, lspec = lib.named("talents", listed)
            if not lref:
                out["notes"].append(f"{listed}: not found among the library's talents, so it isn't priced. Look it up.")
                continue
            lref = lib.current(lref)
            choice = bool(lspec and (bc.ANY.match(lspec) or re.search(r"\s+or\s+|/", lspec)))
            mine = [t for (ref, spec), t in taken.items() if ref == lref and b.offered("talents", listed, ref, spec)]
            for t in mine + ([{"name": listed, "times": 0, "max": None, "new": True}] if choice or not mine else []):
                if any(x["name"] == t["name"] for x in out["talents"]): continue
                mx = t.get("max")
                if t.get("new"):
                    try:
                        mx = b.talent_max(lib.entry(lref).get("fields", {}).get("max"))
                    except Exception:
                        mx = None
                row = {"name": t["name"], "listed": listed, "level": n, "times": t["times"], "max": mx,
                       "next": 100 + (100 * t["times"] if rising else 0), **({"choose": True} if t.get("new") and choice else {})}
                if mx is not None and t["times"] >= mx:
                    row["next"], row["at_max"] = None, True
                out["talents"].append(row)
    out["spells"] = []
    names = [t["name"] for t in m["talents"]]
    if any(bc.norm(n).startswith("petty magic") for n in names):
        k = b.spells_known.get("petty", 0)
        out["spells"].append({"what": "a Petty spell", "known": k, "next": b.spell_price("petty", k)})
    for n in names:
        if bc.norm(n).startswith("arcane magic") and spec_of(n):
            lore = bc.WINDS.get(bc.norm(spec_of(n)), bc.norm(spec_of(n)))
            k = b.spells_known.get(lore, 0) + (b.spells_known.get(bc.norm(spec_of(n)), 0) if lore != bc.norm(spec_of(n)) else 0)
            out["spells"].append({"what": f"a spell of {spec_of(n)}", "known": k, "next": b.spell_price("lore", k)})
    out["creation"] = creation(b, m)
    if record.get("creating"):
        out["starting"] = b.starting()
    out["complete_level"] = completing(b, m, lib, levels, now, price)
    out["unfinished"] = [g for g in m["career"].get("to_complete", [])]
    out["notes"] += [n for n in m["notes"] if "cost table" in n or "Level Advances" in n]
    return out


def completing(b, m, lib, levels, now, price):
    """What the current level still needs (its characteristics, and eight of its available skills, at
    the level's advances; one of its own talents), and the least XP that costs. A level's
    characteristics and available skills include those of the levels below it in the career."""
    if now is None: return None
    t = b.table(bc.LEVEL_ADVANCES)
    want = {str(r[0]).strip(): int(r[1]) for r in t["rows"]}.get(str(now)) if t else None
    if want is None:
        return {"level": now, "note": "The Level Advances table has no row for this level, so what completes it isn't worked out."}
    f = levels[-1][2]                                   # the talent must be one of this level's own
    chars = list(dict.fromkeys(c for _, _, lv in levels for c in lv.get("characteristics", [])))
    need, total = [], 0
    for c in chars:
        adv = m["characteristics"].get(c, {}).get("advances", 0)
        if adv < want:
            p = price("characteristic", adv, want - adv)
            need.append({"what": f"{bc.CHAR_NAME.get(c, c)}: {want - adv} more advances", "xp": p})
            total = None if p is None or total is None else total + p
    have = m["skills"]["basic"] + m["skills"]["advanced"]
    # each skill the character has counts once, under whichever listed name covers it; a name not
    # yet taken, a single choice not yet made, or an open name (another specialisation) starts at 0
    slots = [sl for sl in b.skill_slots() if sl["career"] == lib.current((b.rec.get("careers") or [{}])[-1].get("ref") or "")]
    mine = [(r["name"], r["advances"]) for r in have if any(b.slot_covers(sl, r["ref"], spec_of(r["name"])) for sl in slots)
            and (r["advances"] or spec_of(r["name"]) is None)]
    fresh = [(sl["listed"], 0) for sl in slots if sl["kind"] == "open" or
             not any(b.slot_covers(sl, r["ref"], spec_of(r["name"])) and (r["advances"] or spec_of(r["name"]) is None) for r in have)]
    done = sum(1 for _, g in mine if g >= want)
    short = sorted([(want - g, name, g) for name, g in mine + fresh if g < want])
    for lack, name, g in short[:max(0, min(8, len(mine) + len(fresh)) - done)]:
        p = price("skill", g, lack)
        need.append({"what": f"{name}: {lack} more advances", "xp": p})
        total = None if p is None or total is None else total + p
    lvl = (lib.current((b.rec.get("careers") or [{}])[-1].get("ref") or ""), now)
    if not any(b.in_career("talents", x["ref"], spec_of(x["name"]), lvl) for x in m["talents"]):
        need.append({"what": "one talent of this level", "xp": 100})
        total = None if total is None else total + 100
    return {"level": now, "advances_each": want, "skills_done": done, "needs": need, "least_xp": total}


def text(o):
    L = [f"{o['name']}: {o['career']['name']} {o['career']['level']} ({o['career']['level_name']})",
         f"XP to spend: {o['xp']['current']} ({o['xp']['spent']} spent of {o['xp']['total']})"]
    for k, h in (o.get("house_rules") or {}).items():
        L.append(f"House rule: {h.get('text') or h.get('house_rule')}")
    cost = lambda v: "?" if v is None else f"{v} XP"
    L += ["", "Characteristics (advances; next advance)"]
    L += [f"  {c['name']}: {c['advances']}; {cost(c['next'])}" for c in o["characteristics"]]
    L += ["", "Skills (advances; next advance)"]
    L += [f"  {s['name']}: {s['advances']}; {cost(s['next'])}" + (" (choose which)" if s.get("choose") else "") +
          (f" (the career's {s['chosen_for']}" + (", assumed)" if s.get("assumed") else ")") if s.get("chosen_for") else "") for s in o["skills"]]
    L += ["", "Talents (times taken of Max; price)"]
    L += [f"  {t['name']}: {t['times']} of {t['max'] if t['max'] is not None else '?'}; " +
          ("at its Max" if t.get("at_max") else cost(t["next"])) + (" (choose which)" if t.get("choose") else "") for t in o["talents"]]
    if o.get("creation"):
        L += ["", "Creation (still to give)"]
        for g in o["creation"]:
            left = g["left"] if not isinstance(g["left"], dict) else ", ".join(f"{n} at {v}" for v, n in g["left"].items())
            L.append(f"  {g['kind'].capitalize()}s from the {g['how']} {g['cite']}: " +
                     "; ".join(([f"{left} left"] if left else []) + (["to take: " + ", ".join(g["to_take"])] if g["to_take"] else [])))
            if g["taken"]: L.append("    taken: " + ", ".join(g["taken"]))
            if not g["to_take"]: L.append("    from: " + ", ".join(g["from"]))
    st = o.get("starting")
    if st:
        L += ["", "Starting trappings and money (creation)"]
        def show(it, pad="  "):
            mark = "has" if it["have"] else "to add"
            extra = [f"choose one: {' or '.join(it['choose_one'])}"] if it.get("choose_one") else []
            if isinstance(it.get("qty"), str): extra.append(f"roll {it['qty']} for how many")
            L.append(f"{pad}[{mark}] {it['text']}" + (f" (`{it['ref']}`)" if it.get("ref") else "") + (f": {'; '.join(extra)}" if extra else ""))
            for c in it.get("contains", []): show(c, pad + "    in it: ")
        for k in ("class", "career"):
            if st.get(k) and st[k].get("items") is not None:
                L.append(f"  {st[k]['name']} {st[k]['cite']}:")
                for it in st[k]["items"]: show(it, "    ")
        mo = st.get("money")
        if mo:
            L.append(f"  Money for {mo['status']} {mo['cite']}: " + (f"roll {mo['roll']}" if mo["roll"] else str(mo["amount"])) +
                     f" ({mo['says']}) into `money.{mo['coin']}`")
    if o.get("spells"):
        L += ["", "Spells (known; price of the next)"]
        L += [f"  {x['what']}: {x['known']}; {cost(x['next'])}" for x in o["spells"]]
    c = o.get("complete_level")
    if c:
        L += ["", f"To complete level {c['level']}:"]
        if c.get("note"): L.append("  " + c["note"])
        elif not c["needs"]: L.append("  nothing: it is complete")
        else:
            L += [f"  {n['what']} ({cost(n['xp'])})" for n in c["needs"]]
            L.append(f"  least XP: {cost(c['least_xp'])}")
    for g in o.get("unfinished", []):
        L.append(f"Earlier level unfinished: {g['career']} {g['level']} ({g['level_name']}): {'; '.join(g['missing'])}")
    L.append("\nAnything outside the career can be bought at double the price.")
    L += ["Note: " + n for n in o["notes"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with open(a.record, encoding="utf-8") as f:
        rec = json.load(f)
    o = report(rec, Library(a.library, a.campaign))
    sys.stdout.write(json.dumps(o, indent=1, ensure_ascii=False) + "\n" if a.json else text(o))


if __name__ == "__main__":
    cli(main)
