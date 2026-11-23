"""Detectors: fields an entry's own text states, proposed to the Librarian rather than set.

A plan carries a field the converter couldn't read ("stacks": false on a condition, a skill's
characteristic printed in a bold lead line). Each detector here reads one such field from the
entry's own text, so the next group importing the book needn't rediscover it. A detector only
proposes: the converter lists each proposal with the sentence that says so, and a field is set
(in the plan, with edit_entry.py --plan) once the Librarian confirms it. The patterns are general
English, never a book's text.

    propose(category, kind, name, fields, text, base=None) -> [{"field", "value", "says", "detector"}]

`base` is, for a skill named "Base (Specialisation)", the base skill's index fields from the library
(its characteristic and type), when the converter has the library at hand.

A field the plan already sets is not proposed again; where the text says otherwise, the proposal
is listed with "plan": the plan's value, for the Librarian to look at.
"""
import re

CHARS = ("WS", "BS", "S", "T", "I", "Ag", "Dex", "Int", "WP", "Fel")
CHAR_NAMES = {"Weapon Skill": "WS", "Ballistic Skill": "BS", "Strength": "S", "Toughness": "T", "Initiative": "I",
              "Agility": "Ag", "Dexterity": "Dex", "Intelligence": "Int", "Willpower": "WP", "Fellowship": "Fel"}


def plain_text(blocks):
    """An entry's content as plain text, a block a line, without bold or italic marks."""
    out = []
    def walk(bs):
        for b in bs or []:
            for k in ("text", "title"):
                if isinstance(b.get(k), str): out.append(b[k])
            for r in b.get("rows") or []:
                out.append(" ".join(str(c) for c in r))
            for i in b.get("items") or []:
                out.append(i if isinstance(i, str) else " ".join(str(v) for v in (i.values() if isinstance(i, dict) else i)))
            if isinstance(b.get("content"), list): walk(b["content"])
    walk(blocks)
    return re.sub(r"\*{1,3}|_{2}", "", "\n".join(out))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def stacks(category, kind, name, text, base=None):
    """A condition that says of itself that it doesn't stack ("Unlike most other conditions, Prone
    does not stack"): stacks false. The sentence must be about the condition (its name, "this
    Condition", or "it", just before "does not stack"), so a bonus that doesn't add up ("this bonus
    does not increase") or another condition that doesn't stack named beside it doesn't count."""
    if kind != "condition": return None
    bare = re.escape(re.sub(r"\s*\(.*?\)\s*", "", name or "").strip())
    neg = r"(does not|doesn't|do not|don't|cannot|can't|never)\s+stacks?\b"
    for s in sentences(text):          # the condition is the subject: "Prone does not stack", "The Surprised Condition does not stack"
        if re.search(rf"\b({bare}|this|it)(\s+condition)?\s+{neg}", s, re.I):
            return {"value": False, "says": s}
    return None


def skill_lead(category, kind, name, text, base=None):
    """A skill printed in prose opens with its characteristic and type in a bold lead line
    ("(Int), Advanced, Grouped"): the characteristic, advanced true or false, and grouped true when
    it says Grouped, false when it gives the type without it. Only the first sentence is read (and
    for the characteristic, a sentence saying the Skill is "based on Intelligence"); a
    "Specialisation" there doesn't make the skill grouped (it may be one specialisation of another)."""
    if category != "skills": return None
    first = (sentences(text) or [""])[0][:200]
    got = {}
    m = re.search(r"\((%s)\)" % "|".join(CHARS), first)
    if m: got["characteristic"] = m.group(1)
    if re.search(r"\bAdvanced\b", first): got["advanced"] = True
    elif re.search(r"\bBasic\b", first): got["advanced"] = False
    if re.search(r"\bGrouped\b", first): got["grouped"] = True
    elif "advanced" in got: got["grouped"] = False     # a lead line that gives the type and doesn't say Grouped
    says = first
    if "characteristic" not in got:          # "The Skill is based on Intelligence"
        for s in sentences(text):
            m = re.search(r"\bbased on (%s)\b" % "|".join(CHAR_NAMES), s)
            if m:
                got["characteristic"], says = CHAR_NAMES[m.group(1)], (first + " … " + s if got else s)
                break
    return {"values": got, "says": says} if got else None


def specialisation(category, kind, name, text, base=None):
    """A skill named "Base (Specialisation)" whose base skill is in the library is one specialisation
    of it: the base's characteristic and type, and not grouped itself."""
    if category != "skills" or not base or not re.match(r"^.+?\s*\(.+\)$", name or ""): return None
    got = {k: base[k] for k in ("characteristic", "advanced") if k in base}
    got["grouped"] = False
    return {"values": got, "says": f"{name} is a specialisation of {base.get('name', 'its base skill')}, "
                                    + ", ".join(f"{k} {v}" for k, v in got.items() if k != "grouped")}


DETECTORS = {"stacks": stacks, "skill-lead": skill_lead, "specialisation": specialisation}   # first says first


def base_name(name):
    """"Lore (Runes)" -> "Lore"; None for a name without a specialisation."""
    m = re.match(r"^(.+?)\s*\((.+)\)$", name or "")
    return m.group(1).strip() if m else None


def propose(category, kind, name, fields, text, base=None):
    out, said = [], {}
    for det, fn in DETECTORS.items():
        r = fn(category, kind, name, text, base)
        if not r: continue
        values = r["values"] if "values" in r else {det: r["value"]}
        for field, value in values.items():
            if field in said and said[field] == value: continue        # an earlier detector said the same
            said.setdefault(field, value)
            have = (fields or {}).get(field)
            if have == value: continue
            out.append({"field": field, "value": value, "says": r["says"], "detector": det,
                        **({"plan": have} if field in (fields or {}) else {})})
    return out
