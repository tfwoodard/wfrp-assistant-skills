#!/usr/bin/env python3
"""Rewrite a chapter plan so a chapter-wide "defaults" gives the kind and category most entries share.

    plan_defaults.py PLAN.json [PLAN.json ...] [--write]

For each plan: the category most of its entries have, and the kind, become the plan's "defaults";
an entry with that value loses its own line, and one with another value keeps it (or gains it, where
it relied on the converter's own fallback: no category is "rules", and a rules entry with no kind is
a "procedure"). Every entry must mean the same kind and category afterwards as before, read through
convert_rules.apply_defaults(); a plan where a default can't say the same (a non-rules entry with no
kind at all, under a kind default) gets no default for that key, and the report says so. A default
that saves no lines isn't set. A plan with "defaults" already is left as it is.

Without --write it reports what would change. With it, each changed plan is written in its own
layout (edit_entry.dump_like) and its size printed, for the upload.
"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert_rules import apply_defaults  # noqa: E402
from edit_entry import dump_like  # noqa: E402


def meaning(e):
    """The category and kind the converter gives an entry: (category, kind or None)."""
    cat = e.get("category") or "rules"
    return cat, e.get("kind", "procedure" if cat == "rules" else None)


def compact(plan):
    """(new plan or None, what was done): the plan with defaults, when they save lines."""
    entries = plan.get("entries") or []
    if plan.get("defaults"):
        return None, "has defaults already"
    if not entries:
        return None, "no entries"
    before = [meaning(e) for e in entries]
    out, said = [dict(e) for e in entries], []
    defaults = {}
    for key, i in (("category", 0), ("kind", 1)):
        values = [m[i] for m in before if m[i] is not None]
        if not values: continue
        top, n = collections.Counter(values).most_common(1)[0]
        if key == "kind" and any(m[1] is None for m in before):
            said.append(f"no kind default: {sum(1 for m in before if m[1] is None)} entries have no kind at all")
            continue
        trial = []
        for e, m in zip(out, before):
            e = dict(e)
            if m[i] == top: e.pop(key, None)
            else: e[key] = m[i]
            trial.append(e)
        saved = sum(1 for a, b in zip(out, trial) if key in a and key not in b) - \
            sum(1 for a, b in zip(out, trial) if key not in a and key in b)
        if saved <= 0:
            said.append(f"no {key} default: it would save no lines")
            continue
        out, defaults[key] = trial, top
        said.append(f"{key} {top!r}: {saved} lines fewer")
    if not defaults:
        return None, "; ".join(said) or "nothing to share"
    new = {}
    for k, v in plan.items():
        new[k] = out if k == "entries" else v
        if k == "chapter": new["defaults"] = defaults
    new.setdefault("defaults", defaults)
    after = [meaning(e) for e in apply_defaults(new)["entries"]]
    if after != before:
        raise SystemExit("the defaults would change what an entry means; nothing written")   # never reached, but checked
    rest = [{k: v for k, v in e.items() if k not in ("kind", "category")} for e in entries]
    if rest != [{k: v for k, v in e.items() if k not in ("kind", "category")} for e in out]:
        raise SystemExit("an entry's other keys changed; nothing written")
    return new, "; ".join(said)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plans", nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    for p in a.plans:
        with open(p, encoding="utf-8") as f:
            raw = f.read()
        new, said = compact(json.loads(raw))
        print(f"{p}: {said}")
        if new and a.write:
            text = dump_like(new, raw)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"  wrote {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
