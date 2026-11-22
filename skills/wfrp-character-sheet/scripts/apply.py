#!/usr/bin/env python3
"""Write one purchase or change into a character record, in the record's own format.

    apply.py RECORD --library ROOT --campaign SLUG [--out NEW] [--dry-run] <command> ...

Commands:
  start --name NAME --species NAME [--origin HEADING] --species-how rolled|chosen
        --career NAME --career-how rolled|one-of-three|chosen [--player NAME]
                                              a new record (RECORD must not exist yet): the species,
                                              its origin (a homeland heading such as "Saphery", or
                                              "rules/<entry>#<heading>"), and the first career at
                                              level 1
  initial WS=31 BS=28 ... --how rolled|rearranged|rerolled|allocated
                                              the starting characteristics, all ten, as rolled or
                                              allocated (before anything a talent adds)
  points --fate N --resilience N              the extra points the species gives to share out
  elder --born TIME [--career "TIME=CAREER:rolled|chosen" ...]
                                              an Elder (a creation rule with a grant from
                                              elder-career, such as HEPG's Elders of the Asur): the
                                              Time of birth and the career followed in each Time
                                              lived through; their skills are bought with --how elder
                                              --time TIME
  item "NAME" [--qty N] [--id ID] [--in ID] [--worn] [--stowed] [--enc N] [--notes TEXT]
                                              a trapping: the library's entry when one has that name,
                                              otherwise the name (give --enc); --id names a container,
                                              --in puts it in one
  money [--gc N] [--ss N] [--d N]             the purse: the coins given are set, the rest kept
  finish                                      ends creation: says what creation still had to give
  buy --characteristic CODE [--count N]       advances in a characteristic (WS, Int ...)
  buy --skill "NAME" [--count N]              advances in a skill, named as the books print it:
                                              "Charm", "Lore (Reikland)"
  buy --talent "NAME"                         a talent, once: "Hardy", "Arcane Magic (Hysh)"
  buy --spell "NAME" [--lore LORE]            a spell; --lore for an Arcane spell when the
                                              character has more than one lore
        with --session N, --date YYYY-MM-DD, --notes TEXT, and --how xp|free|talent|species|career|elder
        (free: given in play, no XP; talent: one of the spells Petty Magic gives when it is taken;
        species, career: given at creation, checked against what the creation rules grant; elder:
        from an Elder's career in the Time given with --time)
  log TEXT [--session N] [--date YYYY-MM-DD]   appends a changelog entry

A purchase is added to the record's `advances` (the build prices it: never write the price), the
record is built before and after, and what the purchase did is printed: its price by the rules and
the campaign's house rules, XP to spend before and after, the numbers on the sheet that moved, and
every difference or note the purchase brought with it (a talent past its Max, XP the character
doesn't have, a skill outside the career at double price). The purchase is written all the same:
the group decides what a difference means. --dry-run prints the same and writes nothing.

While a character is being created, start and initial set `xp.total` to the XP the creation steps
gave (the build works it out from the creation rules), and options.py lists what creation still has
to give. An imported record keeps `xp.spent` by hand (its history isn't known), so the price is added to
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


def slug(name):
    return bc.slug(name) or "character"


def find_origin(lib, name):
    """'rules/x#Heading' as given, or the rules entries with a heading of that name that print a
    Skills and Talents list under it."""
    if "#" in name:
        return name
    hits = []
    for _, r in lib.index("rules"):
        ref = f"rules/{r['slug']}"
        try: e = lib.entry(ref)
        except Exception: continue
        if any(b.get("type") == "heading" and bc.norm(b.get("text")) == bc.norm(name) for b in e.get("content", [])):
            try: text = lib.text(lib.section(f"{ref}#{name}"))
            except Exception: continue
            if "**Skills**" in text and "**Talents**" in text: hits.append(f"{ref}#{name}")
    if len(hits) != 1:
        sys.exit(f"'{name}' is the heading of {len(hits)} origins with their own skills and talents" +
                 (f": {', '.join(hits)}. Give one in full." if hits else ". Give it in full: rules/<entry>#<heading>."))
    return hits[0]


def start(lib, a):
    ref = {}
    for what, cat, name in (("species", "species", a.species), ("career", "careers", a.career)):
        r = lib.find(cat, name)
        if not r: sys.exit(f"'{name}' isn't one entry among the {cat} in play.")
        ref[what] = lib.current(r)
    new = {"schema": 2, "slug": slug(a.name), "name": a.name, **({"player": a.player} if a.player else {}),
           "species": {"ref": ref["species"], **({"origin": find_origin(lib, a.origin)} if a.origin else {}), "how": a.species_how},
           "careers": [{"ref": ref["career"], "level": 1, "how": a.career_how}],
           "characteristics": {"initial": {}}, "extra_points": {}, "advances": [], "spells": [], "trappings": [],
           "xp": {"total": 0}, "state": {}, "changelog": [], "creating": True}
    return new, [f"Started {a.name}: {lib.entry(ref['species'])['name']}" +
                 (f" ({new['species']['origin'].split('#')[-1]})" if a.origin else "") + f", {lib.entry(ref['career'])['name']} 1"]


def initial(record, a):
    vals = {}
    for kv in a.values:
        k, _, v = kv.partition("=")
        code = next((c for c in bc.CHARS if c.lower() == k.strip().lower()), None) or bc.NAME_CHAR.get(bc.norm(k))
        if not code or not v.strip().isdigit(): sys.exit(f"'{kv}': write CODE=NUMBER, with a code from {', '.join(bc.CHARS)}")
        vals[code] = int(v)
    missing = [c for c in bc.CHARS if c not in vals]
    if missing: sys.exit(f"all ten are needed; missing {', '.join(missing)}")
    new = copy.deepcopy(record)
    new.setdefault("characteristics", {})["initial"] = vals
    new["characteristics"]["how"] = a.how
    return new, ["Starting characteristics " + ", ".join(f"{c} {vals[c]}" for c in bc.CHARS) + f" ({a.how})"]


def settle_creation_xp(new, lib, said, started=False):
    """At creation the XP total is what the creation steps gave."""
    m = bc.build(copy.deepcopy(new), lib)
    if started:
        said.append("Next: initial (the starting characteristics), points (Fate and Resilience), then buy --how species "
                    "and --how career for what creation gives; options.py lists it.")
        return
    got = (m["xp"].get("at_creation") or {}).get("xp")
    if got is not None:
        new.setdefault("xp", {})["total"] = got
        said.append(f"XP from creation: {got}")
    else:
        said.append("XP from creation: not worked out yet (" + "; ".join(
            f"{s['step']} {s['how'] or 'not said'}" for s in m["xp"]["at_creation"]["steps"] if s["xp"] is None) + ")")
    said += [f"Differs from the rules: {d['text']} `{d['id']}`" for d in m["differences"]]


def item(record, lib, a):
    new = copy.deepcopy(record)
    names = {}
    for _, r in lib.index("trappings"):
        if bc.norm(r["name"]) == bc.norm(a.name): names.setdefault(lib.current(f"trappings/{r['slug']}"), r["name"])
    line = {"ref": next(iter(names))} if len(names) == 1 else {"name": a.name}
    for k in ("qty", "id", "enc", "notes"):
        if getattr(a, k) is not None: line[k] = getattr(a, k)
    for k in ("worn", "stowed"):
        if getattr(a, k): line[k] = True
    if a.in_ and not any(t.get("id") == a.in_ for t in new.get("trappings", [])):
        sys.exit(f"no trapping has the id '{a.in_}': add the container with --id first")
    if a.in_: line["in"] = a.in_
    new.setdefault("trappings", []).append(line)
    said = [f"Trapping: {a.name}" + (f" x{a.qty}" if a.qty else "") + (f" (`{line['ref']}`)" if "ref" in line else "")]
    if "ref" not in line:
        said.append(f"Note: no one trapping in play is named '{a.name}'" + (f" ({len(names)} are)" if names else "") +
                    ("; its Encumbrance is " + (str(a.enc) if a.enc is not None else "not given: add --enc")))
    return new, said


def finish(record, lib):
    new = copy.deepcopy(record)
    b = bc.Builder(copy.deepcopy(record), lib)
    m = b.build()
    said = ["Creation finished"]
    for g in m.get("creation", []):
        left = g["left"] if not isinstance(g["left"], dict) else ", ".join(f"{n} at {v}" for v, n in g["left"].items())
        if left: said.append(f"Left ungiven ({g['rule'].split('/')[-1]}, {g['id']}): {left}")
        if g.get("to_take"): said.append(f"Not taken from the species: {', '.join(g['to_take'])}")
    st = b.starting() or {}
    for k in ("class", "career"):
        for it in ((st.get(k) or {}).get("items") or []):
            for x in [it] + it.get("contains", []):
                if not x["have"]: said.append(f"Not among the trappings: {x['text']} ({k})")
    if not any((new.get("money") or {}).values()): said.append("The purse is empty: starting money not recorded")
    said += [f"Differs from the rules: {d['text']} `{d['id']}`" for d in m["differences"]]
    new.pop("creating", None)
    return new, said


def elder(record, lib, a):
    careers = []
    for spec in a.career or []:
        time, eq, rest = spec.partition("=")
        name, _, how = rest.rpartition(":")
        if not eq or how not in ("rolled", "chosen") or not name.strip():
            sys.exit(f"'{spec}': write TIME=CAREER:rolled or TIME=CAREER:chosen")
        r = lib.find("careers", name.strip())
        if not r: sys.exit(f"'{name.strip()}' isn't one entry among the careers in play.")
        careers.append({"time": time.strip(), "ref": lib.current(r), "how": how})
    new = copy.deepcopy(record)
    new.setdefault("species", {})["elder"] = {"born": a.born, "careers": careers}
    said = [f"An Elder born in the {a.born}" + ("; earlier careers: " + "; ".join(
        f"{c['time']}: {lib.entry(c['ref'])['name']} ({c['how']})" for c in careers) if careers else "")]
    m = bc.build(copy.deepcopy(new), lib)
    for c in (m.get("elder") or {}).get("careers", []):
        if c.get("left"): said.append(f"To give from the {c['time']} career: {c['left']} advances (buy --skill ... --how elder --time \"{c['time']}\")")
    said += [f"Differs from the rules: {d['text']} `{d['id']}`" for d in m["differences"] if d["id"].startswith(("elder:", "creation:"))]
    said += ["Burden: " + t for b in (m.get("elder") or {}).get("burdens", []) for t in b["text"]]
    return new, said


def buy(record, lib, a):
    line, name = line_for(a, lib)
    line["how"] = a.how
    if a.how == "elder":
        if not a.time: sys.exit("--how elder needs --time: the Time of the Elder's career it came from")
        if not a.skill: sys.exit("an Elder's earlier careers give skill advances only")
        line["time"] = a.time
    for k in ("session", "notes"):
        if getattr(a, k) is not None: line[k] = getattr(a, k)
    before = bc.build(copy.deepcopy(record), lib)
    new = copy.deepcopy(record)
    new.setdefault("spells" if a.spell else "advances", []).append(line)
    trial = bc.build(copy.deepcopy(new), lib)
    if a.how == "talent" and not a.spell: sys.exit("--how talent is for a spell that comes with Petty Magic")
    if a.how in ("species", "career") and a.spell: sys.exit(f"a spell isn't given by the {a.how} at creation")
    paid = trial["xp"]["purchases"][-1] if a.how == "xp" and trial["xp"]["purchases"] else {}
    price = paid.get("xp") if a.how == "xp" else 0
    said = [f"{name}" + (f" x{a.count}" if "count" in line and a.count != 1 else "") +
            (": " + ("given in play, no XP" if a.how == "free" else "comes with the talent, no XP" if a.how == "talent" else
                    f"from the {a.how} at creation" if a.how in ("species", "career") else
                    f"from the Elder's career in the {a.time}" if a.how == "elder" else
                    f"{price} XP" if price is not None else "price not worked out"))]
    if a.how == "xp" and price is not None and (new.get("xp") or {}).get("spent") is not None:
        new["xp"]["spent"] += price                    # an imported record keeps its total by hand
    after = bc.build(copy.deepcopy(new), lib)
    said.append(f"XP to spend: {before['xp']['current']} -> {after['xp']['current']}")
    for c in (after.get("elder") or {}).get("careers", []):
        if a.how == "elder" and bc.norm(c["time"]) == bc.norm(a.time or "") and c.get("left") is not None:
            said.append(f"Still to give from the {c['time']} career ({c['name']}): {c['left']} advances")
    for g in after.get("creation", []):
        if g["how"] == a.how and g["kind"] == next(k for k in ("characteristic", "skill", "talent") if k in line) and g["left"]:
            left = g["left"] if not isinstance(g["left"], dict) else ", ".join(f"{n} at {v}" for v, n in g["left"].items())
            said.append(f"Still to give from {g['rule'].split('/')[-1]} ({g['id']}): {left}")
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
    b.add_argument("--how", choices=("xp", "free", "talent", "species", "career", "elder"), default="xp")
    b.add_argument("--time", help="with --how elder: the Time of the Elder's career the advances came from")
    st = sub.add_parser("start")
    for k in ("--name", "--species", "--career"): st.add_argument(k, required=True)
    st.add_argument("--origin"); st.add_argument("--player")
    st.add_argument("--species-how", required=True, choices=("rolled", "chosen"))
    st.add_argument("--career-how", required=True, choices=("rolled", "one-of-three", "chosen"))
    ini = sub.add_parser("initial")
    ini.add_argument("values", nargs="+")
    ini.add_argument("--how", required=True, choices=("rolled", "rearranged", "rerolled", "allocated"))
    it = sub.add_parser("item")
    it.add_argument("name"); it.add_argument("--qty", type=int); it.add_argument("--id"); it.add_argument("--in", dest="in_")
    it.add_argument("--enc", type=int); it.add_argument("--notes")
    it.add_argument("--worn", action="store_true"); it.add_argument("--stowed", action="store_true")
    mo = sub.add_parser("money")
    for k in ("--gc", "--ss", "--d"): mo.add_argument(k, type=int)
    sub.add_parser("finish")
    el = sub.add_parser("elder")
    el.add_argument("--born", required=True); el.add_argument("--career", action="append")
    pt = sub.add_parser("points")
    pt.add_argument("--fate", type=int, required=True); pt.add_argument("--resilience", type=int, required=True)
    for p in (b, sub.add_parser("log")):
        p.add_argument("--session", type=int)
        p.add_argument("--date")
    b.add_argument("--notes")
    sub.choices["log"].add_argument("text")
    a = ap.parse_args()
    lib = Library(a.library, a.campaign)
    if a.cmd == "start":
        if os.path.exists(a.out or a.record): sys.exit(f"{a.out or a.record} exists already: start makes a new record")
        record = None
    else:
        with open(a.record, encoding="utf-8") as f:
            record = json.load(f)
    date = getattr(a, "date", None) or datetime.date.today().isoformat()
    if a.cmd in ("start", "initial", "points", "elder"):
        if a.cmd == "start": new, said = start(lib, a)
        elif a.cmd == "initial": new, said = initial(record, a)
        elif a.cmd == "elder": new, said = elder(record, lib, a)
        else:
            new = copy.deepcopy(record)
            new["extra_points"] = {"fate": a.fate, "resilience": a.resilience}
            said = [f"Extra points: Fate {a.fate}, Resilience {a.resilience}"]
        new.setdefault("changelog", []).append({"date": date, "text": said[0]})
        if a.cmd != "elder" or new.get("creating"):      # an Elder written in later keeps the XP it has
            settle_creation_xp(new, lib, said, a.cmd == "start")
    elif a.cmd in ("item", "money", "finish"):
        if a.cmd == "item": new, said = item(record, lib, a)
        elif a.cmd == "money":
            new = copy.deepcopy(record)
            purse = new.setdefault("money", {})
            for k in ("gc", "ss", "d"):
                if getattr(a, k) is not None: purse[k] = getattr(a, k)
            said = ["Money: " + ", ".join(f"{purse.get(k, 0)} {k}" for k in ("gc", "ss", "d"))]
        else: new, said = finish(record, lib)
        new.setdefault("changelog", []).append({"date": date, "text": said[0]})
    elif a.cmd == "log":
        new = copy.deepcopy(record)
        new.setdefault("changelog", []).append({"date": a.date or datetime.date.today().isoformat(),
                                                **({"session": a.session} if a.session is not None else {}), "text": a.text})
        said = [f"Logged: {a.text}"]
    else:
        if a.count < 1: sys.exit("--count must be 1 or more")
        if (a.talent or a.spell) and a.count != 1: sys.exit("a talent or a spell is bought once at a time")
        new, said = buy(record, lib, a)
    print("\n".join(said))
    if a.dry_run:
        print("(dry run: nothing written)")
    else:
        save(new, a.out or a.record)
        print(f"written: {a.out or a.record}")


if __name__ == "__main__":
    cli(main)
