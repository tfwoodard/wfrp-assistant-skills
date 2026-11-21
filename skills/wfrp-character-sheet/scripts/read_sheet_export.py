#!/usr/bin/env python3
"""Read a character kept by hand in the group's spreadsheet into JSON, to find out what the sheet says.

The output is not a character record and nothing in it is printed: Claude uses it to write a
schema 2 record of choices and library refs (references/character-record.md), and
build_character.py --shown compares the numbers it works out with the sheet's.

    read_sheet_export.py EXPORT.txt > greta.shown.json

EXPORT.txt is the spreadsheet as the Drive connector reads it, or as saved from it: each tab as
"## Sheet name: <tab>" followed by its cells as comma-separated lines. The tabs it knows:

  Description and Talents   Category, Field, , Data rows (Name, Species, Class, Career, Career Level,
                            Career Path, Status, Age, Height, Hair, Eyes, ambitions, party, psychology,
                            corruption), then a "Talent, Count, Max, Test, Description" table
  Crunch                    the characteristics grid (Initial, Advances, Current, Bonus), Fate, Resilience,
                            Movement, Experience, Wealth, Wounds, Encumbrance, Armor by location, then
                            the basic and advanced skill tables side by side
  Trappings                 Name, Enc, Qualities, Locations, AP, Group, Range/Reach, Damage; a name
                            starting "- " is inside the trapping above it, "- - " one deeper
  Spells                    Name, Lore, CN, Range, Target, Duration, Damage, Description

What comes out (keys are absent when the sheet leaves them blank):
  name, species, origin, class, career, career_level, career_path, status, details {age, height, hair, eyes},
  ambitions {short, long}, party {name, short, long, members}, psychology [..], corruption, mutations,
  talents [{name, count, max, tests}], characteristics {WS..Fel: {initial, advances, current, bonus}},
  fate, resilience, movement {base, walk, run}, xp {current, spent, total}, wealth {d, ss, gc},
  wounds, encumbrance {total, max}, armour {head, la, ra, body, ll, rl, shield},
  skills [{name, advanced, career, characteristic, advances, total}],
  trappings [{name, depth, enc, qualities, locations, ap, group, reach, damage}],
  spells [{name, lore, cn, range, target, duration, damage}]
Talent and spell descriptions are the books' words, so they are never copied out.
"""
import csv, io, json, re, sys

CHARS = ("WS", "BS", "S", "T", "I", "Ag", "Dex", "Int", "WP", "Fel")


def tabs(text):
    """{tab name: rows of cells}."""
    out, name, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^## Sheet name:\s*(.+?)\s*$", line)
        if m:
            if name is not None: out[name] = list(csv.reader(io.StringIO("\n".join(buf))))
            name, buf = m.group(1), []
        elif name is not None:
            buf.append(line)
    if name is not None: out[name] = list(csv.reader(io.StringIO("\n".join(buf))))
    return out


def num(v):
    if v is None: return None
    s = str(v).strip()
    if re.fullmatch(r"[-–]?\d+", s): return int(s.replace("–", "-"))
    return s or None


def cell(rows, r, c):
    return rows[r][c].strip() if 0 <= r < len(rows) and 0 <= c < len(rows[r]) else ""


def find(rows, label, start=(0, 0)):
    """(row, column) of the first cell reading `label`, at or after start in reading order."""
    for r in range(start[0], len(rows)):
        for c in range(len(rows[r])):
            if (r, c) >= start and rows[r][c].strip().lower() == label.lower(): return r, c
    return None


def right(rows, label, start=(0, 0)):
    at = find(rows, label, start)
    return num(cell(rows, at[0], at[1] + 1)) if at else None


def below(rows, label, start=(0, 0)):
    at = find(rows, label, start)
    return num(cell(rows, at[0] + 1, at[1])) if at else None


def description(rows, out):
    fields, cat, table = {}, None, None
    for i, r in enumerate(rows):
        r = r + [""] * (5 - len(r))
        if r[0].strip() == "Talent" and r[1].strip() == "Count":
            table = i; break
        if r[0].strip(): cat = r[0].strip()
        if r[1].strip(): fields.setdefault(cat, []).append((r[1].strip(), r[3].strip()))
    b = dict(fields.get("Basics", []))
    sp = re.match(r"^(.*?)\s*\((.+)\)\s*$", b.get("Species", ""))
    out.update({"name": b.get("Name"), "species": sp.group(1) if sp else b.get("Species"),
                "origin": sp.group(2) if sp else None, "class": b.get("Class"), "career": b.get("Career"),
                "career_level": b.get("Career Level"), "career_path": b.get("Career Path"), "status": b.get("Status")})
    out["details"] = {k.lower(): num(b[k]) for k in ("Age", "Height", "Hair", "Eyes") if b.get(k)}
    a = dict(fields.get("Ambitions", []))
    out["ambitions"] = {"short": a.get("Short-term"), "long": a.get("Long-term")}
    p = dict(fields.get("Party", []))
    out["party"] = {"name": p.get("Name"), "short": p.get("Short-term"), "long": p.get("Long-term"), "members": p.get("Members")}
    out["psychology"] = [f"{k}: {v}" if v else k for k, v in fields.get("Psychology", [])]
    c = dict(fields.get("Corruption", []))
    out["corruption"], out["mutations"] = num(c.get("Points")), c.get("Mutations") or None
    out["talents"] = []
    for r in rows[table + 1:] if table is not None else []:
        r = r + [""] * (4 - len(r))
        if r[0].strip():
            out["talents"].append({"name": r[0].strip(), "count": num(r[1]), "max": num(r[2]), "tests": r[3].strip() or None})


def crunch(rows, out):
    head = find(rows, "WS")
    out["characteristics"] = {}
    if head:
        cols = {rows[head[0]][c].strip(): c for c in range(len(rows[head[0]])) if rows[head[0]][c].strip() in CHARS}
        for label in ("Initial", "Advances", "Current", "Bonus"):
            at = next((r for r in range(head[0], min(head[0] + 8, len(rows))) if cell(rows, r, 0) == label), None)
            for ch, c in cols.items():
                out["characteristics"].setdefault(ch, {})[label.lower()] = num(cell(rows, at, c)) if at is not None else None
    out["fate"], out["resilience"] = below(rows, "Fate"), below(rows, "Resilience")
    out["movement"] = {"base": right(rows, "Base"), "walk": right(rows, "Walk"), "run": right(rows, "Run")}
    xp = find(rows, "Experience")
    if xp:
        out["xp"] = {k.lower(): right(rows, k, (xp[0], xp[1])) for k in ("Current", "Spent", "Total")}
    out["wealth"] = {"d": right(rows, "D"), "ss": right(rows, "SS"), "gc": right(rows, "GC")}
    out["wounds"] = below(rows, "Wounds")
    enc = find(rows, "Encumbrance")
    if enc:
        out["encumbrance"] = {"total": right(rows, "Total", enc), "max": right(rows, "Max", enc)}
    arm = find(rows, "Armor") or find(rows, "Armour")
    if arm:
        names = [cell(rows, arm[0] - 1, c) for c in range(arm[1] + 1, arm[1] + 8)]
        out["armour"] = {n.lower(): num(cell(rows, arm[0], arm[1] + 1 + i)) for i, n in enumerate(names) if n}
    sk = find(rows, "Basic Skill Name")
    out["skills"] = []
    if sk:
        h = rows[sk[0]]
        starts = [c for c in range(len(h)) if h[c].strip().endswith("Skill Name")]
        for s in starts:
            end = next((x for x in starts if x > s), len(h))
            col = {h[c].strip(): c for c in range(s, end) if h[c].strip()}
            for r in range(sk[0] + 1, len(rows)):
                name = cell(rows, r, s)
                if not name: continue
                out["skills"].append({
                    "name": re.sub(r"\s+-\s+.*$", "", name),           # "Channelling (Hysh) - Light"
                    "advanced": h[s].strip().startswith("Advanced"),
                    "career": cell(rows, r, col.get("Cur", -1)).upper() == "Y",
                    "characteristic": cell(rows, r, col.get("Characteristic", -1)) or None,
                    "advances": num(cell(rows, r, col.get("Adv", -1))),
                    "total": num(cell(rows, r, col.get("Skill", -1)))})


def table(rows, keys):
    out = []
    for r in rows[1:]:
        r = r + [""] * (len(keys) - len(r))
        if not r[0].strip(): continue
        out.append({k: num(r[i]) for i, k in enumerate(keys) if k and num(r[i]) is not None})
    return out


def read(text):
    t, out = tabs(text), {}
    if "Description and Talents" in t: description(t["Description and Talents"], out)
    if "Crunch" in t: crunch(t["Crunch"], out)
    out["trappings"] = []
    for row in table(t.get("Trappings", []), ("name", "enc", "qualities", "locations", "ap", "group", "reach", "damage")):
        m = re.match(r"^((?:-\s+)*)(.*)$", str(row["name"]))
        row["depth"], row["name"] = m.group(1).count("-"), m.group(2).strip()
        out["trappings"].append(row)
    # the last column is the book's description: left behind
    out["spells"] = table(t.get("Spells", []), ("name", "lore", "cn", "range", "target", "duration", "damage", None))
    out["tabs_not_read"] = [n for n in t if n not in ("Description and Talents", "Crunch", "Trappings", "Spells")]
    return {k: v for k, v in out.items() if v not in (None, {}, "")}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        json.dump(read(f.read()), sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
