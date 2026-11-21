#!/usr/bin/env python3
"""Roll on the library's tables and dice, showing every die.

    roll.py --library ROOT --campaign SLUG table NAME [--column COLUMN] [--result N] [--json]
    roll.py --library ROOT --campaign SLUG dice EXPR [--json]                  # "6d10", "2d10+30"
    roll.py --library ROOT --campaign SLUG characteristics --species NAME [--json]

table: the table entry in play by name ("Random Species", "Random Class and Career"); the dice are
the entry's own (`fields.roll`, d100 when it says nothing). A table with one column of ranges
("01–90") is read from that column; one with a column of ranges per species or homeland needs
--column (the closest heading is used, and said). A blank cell repeats the one above it, so a
career's row gives its class. --result N reads the row for a roll the player made with real dice
instead of rolling.

characteristics: 2d10 (or whatever the species' formula says) for each characteristic, plus the
species' modifier, with the rolls in order so they can be kept (`initial ... --how rolled`) or
rearranged (`--how rearranged`). It prints the apply.py initial arguments.

Nothing is written. --seed N makes the rolls repeatable (tests).
"""
import argparse, difflib, json, os, random, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
from library import Library, cli, norm  # noqa: E402

RANGE = re.compile(r"^\s*(\d{1,3})\s*(?:[–—-]\s*(\d{1,3}))?\s*$")


def span(cell, top):
    """'01–03' -> (1, 3); '98–00' -> (98, 100); '05' -> (5, 5); None when it isn't a range."""
    m = RANGE.match(str(cell or ""))
    if not m: return None
    lo, hi = int(m.group(1)), int(m.group(2) if m.group(2) is not None else m.group(1))
    if hi == 0: hi = top
    if lo == 0: lo = top
    return lo, hi


def dice(expr, rng):
    """Roll "2d10+30": (total, [(term, [dice] or None, value)])."""
    parts, total = [], 0
    for sign, term in re.findall(r"([+-]?)\s*(\d*d\d+|\d+)", expr.replace(" ", "")):
        k = -1 if sign == "-" else 1
        m = re.match(r"(\d*)d(\d+)", term)
        if m:
            n, d = int(m.group(1) or 1), int(m.group(2))
            got = [rng.randint(1, d) for _ in range(n)]
            parts.append((sign + term, got, k * sum(got)))
        else:
            parts.append((sign + term, None, k * int(term)))
        total += parts[-1][2]
    if not parts: raise SystemExit(f"'{expr}' isn't dice: write it as 2d10+30 or 6d10")
    return total, parts


def shown(parts):
    return " ".join(f"{t} ({'+'.join(map(str, g))})" if g else t for t, g, _ in parts)


def table(lib, name, column, result, rng):
    ref = lib.find("tables", name) or lib.find("tables", name + " Table")
    if not ref and re.fullmatch(r"(tables/)?[a-z0-9-]+", name) and any(r["slug"] == name.split("/")[-1] for _, r in lib.index("tables")):
        ref = "tables/" + name.split("/")[-1]
    if not ref:
        near = sorted(r["name"] for _, r in lib.index("tables") if norm(name) in norm(r["name"]))[:8]
        raise SystemExit(f"'{name}' isn't one table in play" + (f": did you mean {', '.join(near)}?" if near else "."))
    ref = lib.current(ref)
    e = lib.entry(ref)
    t = next((b for b in e.get("content", []) if b.get("type") == "table"), None)
    if not t: raise SystemExit(f"{ref} has no table.")
    die = str(e.get("fields", {}).get("roll") or "d100")
    top = int(re.search(r"d(\d+)", die).group(1)) if re.search(r"d(\d+)", die) else 100
    cols = t["columns"]
    def ranges(i):           # every cell a range, a dash (none on this column) or empty, and some ranges
        cells = [str(r[i]).strip() for r in t["rows"] if i < len(r)]
        return any(span(c, top) for c in cells) and all(span(c, top) or c in ("", "–", "—", "-") for c in cells)
    ranged = [i for i in range(len(cols)) if ranges(i)]
    if not ranged: raise SystemExit(f"{e['name']}: no column of ranges to roll on.")
    said = []
    if len(ranged) == 1 and not column:
        col = ranged[0]
    else:
        if not column:
            raise SystemExit(f"{e['name']} has a column of ranges for each of: {', '.join(cols[i] for i in ranged)}. Give --column.")
        score = {i: difflib.SequenceMatcher(None, norm(column), norm(cols[i])).ratio() for i in ranged}
        col = max(score, key=score.get)
        if score[col] < 0.6: raise SystemExit(f"'{column}' isn't one of: {', '.join(cols[i] for i in ranged)}.")
        if norm(cols[col]) != norm(column): said.append(f"column: {cols[col]}")
    if result is None:
        result, parts = dice(die if re.match(r"\d", die) else "1" + die, rng)
        said.append(f"rolled {die}: {result}")
    else:
        said.append(f"the player's roll: {result}")
    carry, row = {}, None
    for r in t["rows"]:
        for i, c in enumerate(r):
            if i not in ranged and str(c).strip(): carry[i] = c
        s = span(r[col], top) if col < len(r) else None
        if s and s[0] <= result <= s[1]:
            row = {cols[i]: carry.get(i, "") for i in range(len(cols)) if i not in ranged}
            break
    return {"table": e["name"], "ref": ref, "cite": bc.cite(e, bc.chapter_titles(lib)), "column": cols[col], "roll": result,
            "row": row, "said": said}


def characteristics(lib, species, rng):
    ref = lib.find("species", species)
    if not ref: raise SystemExit(f"'{species}' isn't one species in play.")
    e = lib.entry(lib.current(ref))
    f = e.get("fields", {}).get("characteristics") or {}
    out = []
    for c in bc.CHARS:
        if c not in f: raise SystemExit(f"{e['name']} gives no formula for {c}.")
        m = re.match(r"\s*(\d*d\d+)\s*([+-]\s*\d+)?\s*$", str(f[c]))
        if not m: raise SystemExit(f"{e['name']}: {c} is '{f[c]}', which isn't dice plus a number.")
        total, parts = dice(m.group(1), rng)
        add = int((m.group(2) or "0").replace(" ", ""))
        out.append({"code": c, "formula": f[c], "dice": parts[0][1], "rolled": total, "add": add, "value": total + add})
    return {"species": e["name"], "rolls": out}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--seed", type=int)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table"); t.add_argument("name"); t.add_argument("--column"); t.add_argument("--result", type=int)
    d = sub.add_parser("dice"); d.add_argument("expr")
    c = sub.add_parser("characteristics"); c.add_argument("--species", required=True)
    for p in (t, d, c):
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--seed", type=int, default=argparse.SUPPRESS)
    a = ap.parse_args()
    rng = random.Random(a.seed) if a.seed is not None else random.SystemRandom()
    lib = Library(a.library, a.campaign)
    if a.cmd == "table":
        out = table(lib, a.name, a.column, a.result, rng)
        text = [f"{out['table']} {out['cite']}: " + "; ".join(out["said"]),
                ("  " + ", ".join(f"{k}: {v}" for k, v in out["row"].items())) if out["row"] else "  no row covers it"]
    elif a.cmd == "dice":
        total, parts = dice(a.expr, rng)
        out = {"expr": a.expr, "total": total, "dice": [{"term": t, "dice": g, "value": v} for t, g, v in parts]}
        text = [f"{a.expr}: {shown(parts)} = {total}"]
    else:
        out = characteristics(lib, a.species, rng)
        text = [f"{out['species']}:"] + [f"  {bc.CHAR_NAME[r['code']]}: {r['formula']}: " + "+".join(map(str, r["dice"])) +
                                          f" = {r['rolled']}, +{r['add']} = {r['value']}" for r in out["rolls"]]
        text += ["Rolled, in order: " + ", ".join(str(r["rolled"]) for r in out["rolls"]),
                 "Kept: apply.py ... initial " + " ".join(f"{r['code']}={r['value']}" for r in out["rolls"]) + " --how rolled",
                 "Rearranged: move the rolled numbers between characteristics, add each one's modifier, and use --how rearranged."]
    print(json.dumps(out, ensure_ascii=False, indent=1) if a.json else "\n".join(text))


if __name__ == "__main__":
    cli(main)
