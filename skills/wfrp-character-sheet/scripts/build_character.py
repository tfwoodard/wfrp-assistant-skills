#!/usr/bin/env python3
"""Work out a character's sheet from their record and the library's rules.

The record (schema 2, references/character-record.md) holds the character's choices: species and
origin, careers and levels, starting characteristics, every advance and where it came from,
talents, spells, trappings, and the effects rules have on numbers. Everything else comes from the
library each time: species formulas, career levels, skill characteristics, talent maximums, spell
and weapon numbers, the XP cost tables. So a corrected or newly imported source shows up the next
time a sheet is built.

    build_character.py RECORD.json --library ROOT --campaign SLUG            # the model, as JSON
    build_character.py RECORD.json --library ROOT --campaign SLUG --md       # the readable sheet
    build_character.py RECORD.json ... --shown SHEET.json                    # and compare with a
                                                    # sheet someone kept by hand (read_sheet_export.py)

The build never changes a number to fit a rule. Where the record and the rules disagree it says so
in the model's "differences", each with an id and the rule it comes from. A difference the group
has settled is written down once, in the record's "exceptions" or the campaign's "house_rules"
(by id), and from then on it is listed under "accepted" instead. Things the build could not work
out are in "notes": nothing is left out without saying so.
"""
import argparse, ast, fnmatch, json, operator, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from library import Library, RefError, cite, chapter_titles, cli, norm  # noqa: E402

CHARS = ("WS", "BS", "S", "T", "I", "Ag", "Dex", "Int", "WP", "Fel")
CHAR_NAME = {"WS": "Weapon Skill", "BS": "Ballistic Skill", "S": "Strength", "T": "Toughness",
             "I": "Initiative", "Ag": "Agility", "Dex": "Dexterity", "Int": "Intelligence",
             "WP": "Willpower", "Fel": "Fellowship"}
NAME_CHAR = {norm(v): k for k, v in CHAR_NAME.items()}
BONUS = {c + "B": c for c in CHARS}                       # SB, TB, WPB ... as the books abbreviate them
LOCATIONS = ("Head", "Left Arm", "Right Arm", "Body", "Left Leg", "Right Leg")
# the eight winds and the lores they are (the Rulebook's magic chapter names both)
WINDS = {"hysh": "light", "chamon": "metal", "ghyran": "life", "azyr": "heavens", "ulgu": "shadows",
         "shyish": "death", "aqshy": "fire", "ghur": "beasts"}
# where the numbers the build needs are printed: (entry, table title)
COSTS = ("rules/advancing-through-your-career", "Characteristic and Skill Improvement XP Costs")
LEVEL_ADVANCES = ("rules/changing-career", "Level Advances")
MOVEMENT = ("rules/movement-attribute", "Movement")
RULE = {"non-career": "rules/advancing-through-your-career#Non-career Advances",
        "talents": "rules/advancing-through-your-career#Talent Advances",
        "completing": "rules/changing-career#Completing a Career",
        "encumbrance": "rules/encumbrance", "worn": "rules/encumbrance#Worn Items",
        "corruption": "rules/corrupting", "attributes": "rules/step-3-attributes"}
HOW = ("species", "career", "xp", "free", "imported")
# What a campaign's house rule may set (campaign.json house_rules[].set, layout §8); the first is the books' way.
SETTINGS = {"talent_cost": ("rising", "flat"),                       # 100, 200, 300 ... or 100 each time
            "talents_from": ("current-level", "levels-reached")}     # which career levels sell their talents
# the numbers a rule's effect can add to (ADR 0005)
TARGETS = set(CHARS) | {"wounds", "movement", "fate", "resilience", "encumbrance", "corruption", "spell_cost", "xp"}
SCALED = {"spell_cost"}            # targets an effect multiplies ("multiply": 0.5) rather than adds to
# where the price of a new spell is printed: (talent, table title), by the spell's kind
SPELL_COSTS = {"petty": ("Petty Magic", "Petty Magic Spell Costs"), "lore": ("Arcane Magic", "Arcane Magic Spell Costs"),
               "arcane": ("Arcane Magic", "Arcane Magic Spell Costs")}
SPELL_HOW = ("talent", "xp", "free", "imported")
# the rules that say what creation gives (their "grants", ADR 0007): what a record's `species` and
# `career` advance lines are checked against, with any entry in play that adds to them
CREATION_RULES = ("rules/species-skills-and-talents", "rules/career-skills-and-talents", "rules/advance-characteristics")
GRANT_FROM = ("species", "first-career-level")
# the creation steps that can earn XP, the rule that says how much (its "xp" effects, ADR 0005), and
# the ways the record can say the step was settled
CREATION = (("species", "rules/step-1-species", ("rolled", "chosen")),
            ("career", "rules/step-2-class-and-career", ("rolled", "one-of-three", "chosen")),
            ("characteristics", "rules/characteristics", ("rolled", "rearranged", "rerolled", "allocated")))
ANY = re.compile(r"^any\b", re.I)
ONE = re.compile(r"^any one\b|\s+or\s+|\s*/\s*", re.I)     # a listed name that is one choice: "Lore (Any One)", "Art (A or B)"
ROLL = re.compile(r"^\d+(\s*[–-]\s*\d+)?$")          # a table's dice column: "36–40"


def split_list(text):
    """"A, B (C, D), E" -> ["A", "B (C, D)", "E"]."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(": depth += 1
        if ch == ")": depth = max(0, depth - 1)
        if ch == "," and not depth:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


class Sums:
    """Arithmetic in the books' own shorthand: "SB+(2 × TB)+WPB", "TB * times", "2d10+30" (as a range)."""
    OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.FloorDiv: operator.floordiv}

    def __init__(self, names):
        self.names = names

    def value(self, text):
        src = str(text).replace("×", "*").replace("–", "-").replace("−", "-")
        return self._eval(ast.parse(src, mode="eval").body)

    def _eval(self, n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
        if isinstance(n, ast.Name):
            if n.id not in self.names: raise ValueError(f"'{n.id}' isn't a number the sheet has")
            return self.names[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in self.OPS:
            return self.OPS[type(n.op)](self._eval(n.left), self._eval(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub): return -self._eval(n.operand)
        raise ValueError("only numbers, names, + - * // and brackets")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", norm(text or "")).strip("-")


def dice_range(formula):
    """(lowest, highest) a roll like "2d10+30" can give, or None when it isn't one."""
    m = re.fullmatch(r"\s*(\d+)d(\d+)\s*(?:([+\-–])\s*(\d+))?\s*", str(formula))
    if not m: return None
    n, d, sign, k = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4) or 0)
    k = k if sign in (None, "+") else -k
    return n + k, n * d + k


class Builder:
    def __init__(self, record, lib):
        self.rec, self.lib = record, lib
        self.diff, self.notes, self.applied, self.gaps = [], [], [], []
        self.titles = None

    # ------------------------------------------------------------------ reporting
    def differ(self, id, text, rule=None):
        if not any(d["id"] == id for d in self.diff):
            self.diff.append({"id": id, "text": text, **({"rule": rule} if rule else {})})

    def note(self, text):
        if text not in self.notes: self.notes.append(text)

    def cite(self, ref):
        try:
            e = self.lib.entry(ref)
        except RefError:
            return ""
        if self.titles is None: self.titles = chapter_titles(self.lib)
        return cite(e, self.titles)

    def entry(self, ref, what):
        """The entry a record line names (the one in play, when another replaces it), or None with a
        difference saying it isn't there."""
        if not ref: return None, None
        cur = self.lib.current(ref.split("#", 1)[0])
        try:
            return cur, self.lib.entry(cur)
        except RefError as e:
            self.differ(f"missing:{ref}", f"{what}: {e}")
            return cur, None

    def table(self, where):
        try:
            return self.lib.table(*where)
        except RefError as e:
            self.note(f"The '{where[1]}' table isn't in the library ({e}), so what depends on it isn't worked out.")
            return None

    # ------------------------------------------------------------------ what a list offers
    def offered(self, category, listed, ref, spec):
        """Does a name as a species or career prints it ("Lore (Any One)", "Art (Calligraphy or
        Engraving)", "Melee (Basic)") cover this skill or talent?"""
        lref, lspec = self.lib.named(category, listed)
        if not lref:
            return False
        if self.lib.current(lref) != ref:
            return False
        if lspec is None:
            return True
        if spec is None:                # the bare line of a grouped skill isn't any one specialisation
            return False
        if ANY.match(lspec):
            return True
        return norm(spec) in [norm(o) for o in re.split(r"\s+or\s+|\s*/\s*", lspec)]

    def lists(self):
        """What the species (or the origin, when one is chosen) and each career level offer."""
        if hasattr(self, "_lists"): return self._lists
        sp = {"skills": [], "talents": [], "from": None}
        ref, e = self.entry((self.rec.get("species") or {}).get("ref"), "Species")
        if e:
            f = e.get("fields", {})
            sp = {"skills": list(f.get("skills", [])), "talents": list(f.get("talents", [])), "from": ref}
        origin = (self.rec.get("species") or {}).get("origin")
        if origin:
            o = self.origin(origin)
            if o: sp = {**o, "from": origin}
        levels = []                                   # (career ref, level, fields of that level)
        for c in self.rec.get("careers", []):
            cref, ce = self.entry(c.get("ref"), "Career")
            if not ce: continue
            adv = ce.get("fields", {}).get("advances", {})
            for n in range(1, int(c.get("level", 1)) + 1):
                if str(n) in adv: levels.append((cref, n, adv[str(n)]))
        self._lists = {"species": sp, "levels": levels}
        return self._lists

    def origin(self, ref):
        """A homeland's own skills and talents, printed as "**Skills**: ... **Talents**: ..." under its
        heading in a rules entry; they stand in for the species' lists."""
        try:
            text = self.lib.text(self.lib.section(ref))
        except RefError as e:
            self.differ(f"missing:{ref}", f"Origin: {e}")
            return None
        m = re.search(r"\*\*Skills\*\*:?\s*(.*?)\s*\*\*Talents\*\*:?\s*([^\n]*)", text, re.S)
        if not m:
            self.note(f"{ref}: no Skills and Talents lists found under that heading, so the species' own are used.")
            return None
        talents = []
        for t in split_list(m.group(2)):
            opts = [o.strip() for o in re.split(r"\s*\*?\bor\b\*?\s*", t) if o.strip()]
            talents.append(opts[0] if len(opts) == 1 else {"choose_one": opts})
        return {"skills": split_list(m.group(1)), "talents": talents}

    def skill_slots(self):
        """The skills each career level reached lists, one slot per listed name:
        [{career, level, listed, kind, choice, assumed}]. A name is *exact* ("Charm", "Lore (Magic)"),
        *open* ("Lore (Any)": every specialisation), or *one* choice ("Lore (Any One)", "Art
        (Calligraphy or Engraving)"): the one specialisation the character took for it. The record
        says which on the career (`choices`: {"Lore (Any One)": "Empire"}); without that it is taken
        to be the most advanced skill the name covers that no exact name or earlier choice of the
        career already accounts for, and the sheet says it was assumed."""
        if hasattr(self, "_slots"): return self._slots
        have = {}
        for a in self.ledger:
            if a.get("skill"):
                k = (self.lib.current(a["skill"]), a.get("specialisation"))
                have[k] = have.get(k, 0) + int(a.get("count", 0))
        choices = {self.lib.current(c.get("ref") or ""): c.get("choices") or {} for c in self.rec.get("careers", [])}
        slots, seen = [], set()
        for cref, n, f in self.lists()["levels"]:
            for listed in f.get("skills", []):
                if (cref, listed) in seen: continue
                seen.add((cref, listed))
                lref, lspec = self.lib.named("skills", listed)
                kind = "exact" if not lspec else "one" if ONE.search(lspec) else "open" if ANY.match(lspec) else "exact"
                slots.append({"career": cref, "level": n, "listed": listed, "kind": kind, "choice": None, "assumed": False,
                              "ref": self.lib.current(lref) if lref else None})
        used = set()
        for sl in slots:
            if sl["kind"] != "one": continue
            said = choices.get(sl["career"], {}).get(sl["listed"])
            if said:
                if not self.offered("skills", sl["listed"], sl["ref"], said):
                    self.differ(f"career-choice:{slug(sl['listed'])}", f"The record takes {said} for the career's {sl['listed']}, "
                                f"which that name doesn't cover.", sl["career"])
                    continue
                sl["choice"] = (sl["ref"], next((sp for (r, sp) in have if r == sl["ref"] and sp and norm(sp) == norm(said)), said))
            else:
                exact = {(x["ref"], norm(self.lib.named("skills", x["listed"])[1] or "")) for x in slots
                         if x["career"] == sl["career"] and x["kind"] == "exact"}
                cand = sorted(((-v, sp) for (r, sp), v in have.items() if r == sl["ref"] and sp and
                               self.offered("skills", sl["listed"], r, sp) and (r, norm(sp)) not in exact and (sl["career"], r, sp) not in used))
                if cand:
                    sl["choice"], sl["assumed"] = (sl["ref"], cand[0][1]), True
            if sl["choice"]: used.add((sl["career"],) + sl["choice"])
        assumed = [f"{x['listed']} = {self.lib.entry(x['ref'])['name']} ({x['choice'][1]})" for x in slots if x["assumed"]]
        if assumed:
            self.note("Taken as the career's choices, from the advances in the record: " + "; ".join(assumed) +
                      ". Write them on the career in the record (`choices`) to settle them.")
        self._slots = slots
        return slots

    def slot_covers(self, sl, ref, spec):
        if sl["kind"] == "one":
            return bool(sl["choice"]) and sl["choice"][0] == ref and spec is not None and norm(sl["choice"][1]) == norm(spec)
        return self.offered("skills", sl["listed"], ref, spec)

    def in_career(self, category, ref, spec, talents_level=None):
        """The career level that lists it, for skills from any level reached; talents only from the
        current level when talents_level is given. A skill listed as one choice is in the career
        only as the specialisation chosen for it (skill_slots)."""
        if category == "skills":
            return next(((sl["career"], sl["level"]) for sl in self.skill_slots() if self.slot_covers(sl, ref, spec)), None)
        key = "talents"
        for cref, n, f in self.lists()["levels"]:
            if talents_level is not None and (cref, n) != talents_level: continue
            if any(self.offered(category, x, ref, spec) for x in f.get(key, [])):
                return cref, n
        return None

    def from_species(self, category, ref, spec):
        sp = self.lists()["species"]
        for x in sp["skills" if category == "skills" else "talents"]:
            for name in (x.get("choose_one", []) if isinstance(x, dict) else [x]):
                if self.offered(category, name, ref, spec): return True
        return False

    # ------------------------------------------------------------------ the build
    def build(self):
        rec = self.rec
        if rec.get("schema") != 2:
            self.note(f"The record is schema {rec.get('schema')}; this build reads schema 2 (references/character-record.md).")
        m = {"name": rec.get("name"), "player": rec.get("player"), "slug": rec.get("slug")}
        self.ledger = rec.get("advances", [])
        for i, a in enumerate(self.ledger):
            if a.get("how") not in HOW:
                self.differ(f"advance-how:{i}", f"Advance {i + 1} says how it was gained as '{a.get('how')}'; "
                            f"it must be one of: {', '.join(HOW)}.")
        m["species"] = self.species()
        m["career"] = self.career()
        m["characteristics"] = self.characteristics()
        self.names = {c: v["current"] for c, v in m["characteristics"].items()}
        self.names.update({b: m["characteristics"][c]["bonus"] for b, c in BONUS.items()})
        m.update(self.attributes())
        m["talents"] = self.talents()
        m["skills"] = self.skills()
        m["spells"] = self.spells(m["talents"])
        m["trappings"], m["armour"], m["encumbrance"] = self.trappings()
        m["xp"] = self.xp()
        m["creation"] = self.creation()
        self.levels_complete(m)
        for k in ("money", "ambitions", "details"):
            if rec.get(k) not in (None, "", [], {}): m[k] = rec[k]
        for k in ("psychology", "mutations"):          # plain words as written; table rows with what they say
            named = iter([r for r in self.rows() if r["list"] == k])
            items = []
            for x in rec.get(k) or []:
                if not isinstance(x, dict): items.append(x)
                elif self.lib.current(x.get("table") or "") and any(r["list"] == k and norm(r["name"]) == norm(x.get("row") or "") for r in self.rows()):
                    r = next(named)
                    items.append({kk: r[kk] for kk in ("name", "table", "cells", "why", "cite", "notes") if r.get(kk)})
            if items: m[k] = items
        st = rec.get("state", {})
        m["state"] = {"wounds_taken": st.get("wounds_taken", 0), "fortune_spent": st.get("fortune_spent", 0),
                      "resolve_spent": st.get("resolve_spent", 0), "conditions": st.get("conditions", []),
                      "critical_wounds": st.get("critical_wounds", []), "insanities": st.get("insanities", [])}
        m["effects"] = self.applied
        m["career"]["to_complete"] = self.gaps        # levels left behind unfinished, whether or not that is accepted
        for k in SETTINGS: self.setting(k)
        m["house_rules"] = self.set_by
        m["differences"], m["accepted"] = self.settle()
        m["notes"] = self.notes
        m["incomplete"] = list(rec.get("incomplete", []))
        return m

    def species(self):
        sp = self.rec.get("species") or {}
        ref, e = self.entry(sp.get("ref"), "Species")
        self.sp_fields = (e or {}).get("fields", {})
        out = {"ref": ref, "name": (e or {}).get("name"), "cite": self.cite(ref) if e else ""}
        if sp.get("origin"):
            out["origin"] = sp["origin"].split("#")[-1].split("›")[-1].strip()
            out["origin_ref"] = sp["origin"]
        return out

    def career(self):
        cs = self.rec.get("careers", [])
        if not cs:
            self.differ("career", "The record names no career.")
            return {}
        path = []
        for c in cs:
            ref, e = self.entry(c.get("ref"), "Career")
            f = (e or {}).get("fields", {})
            lv = int(c.get("level", 1))
            names = f.get("levels", [])
            if e and not 1 <= lv <= len(names):
                self.differ(f"career-level:{ref}", f"{e['name']} has {len(names)} levels; the record says level {lv}.")
            path.append({"ref": ref, "name": (e or {}).get("name"), "class": f.get("class"), "level": lv,
                         "level_name": names[lv - 1] if 0 < lv <= len(names) else None,
                         "levels": names[:lv], "status": (f.get("status") or [None] * lv)[lv - 1] if lv <= len(f.get("status", [])) else None,
                         "earning_skill": f.get("earning_skill"), "cite": self.cite(ref) if e else "",
                         "species": f.get("species", [])})
        cur = dict(path[-1])
        sp = self.rec.get("species") or {}
        sref, se = self.entry(sp.get("ref"), "Species")
        if se and cur.get("species"):
            mine = {norm(se["name"])} | {norm(a) for a in se.get("aliases", [])}
            if not mine & {norm(s) for s in cur["species"]}:
                self.differ(f"career-species:{cur['ref']}",
                            f"{cur['name']} is listed for {', '.join(cur['species'])}; the character is {se['name']}.",
                            cur["ref"])
        cur.pop("species", None)
        cur["path"] = [{k: p[k] for k in ("name", "class", "levels")} for p in path]
        self.current_level = (cur["ref"], cur["level"])
        return cur

    def used(self):
        """{ref: (entry, times)}: the entries this character uses (species, careers, talents, skills,
        spells, trappings the record names) and every entry in play that adds to one of them. Their
        formulas are the only ones evaluated (ADR 0005). `times` is how often a talent was taken."""
        if hasattr(self, "_used"): return self._used
        rec, refs = self.rec, {}
        self.specs = {}                       # ref -> the specialisations taken of it ("Magical Prodigy")
        def use(ref, what, times=1, spec=None):
            if not ref: return
            cur, e = self.entry(ref, what)
            if e:
                refs[cur] = (e, refs.get(cur, (e, 0))[1] + times)
                if spec: self.specs.setdefault(cur, set()).add(norm(spec))
        use((rec.get("species") or {}).get("ref"), "Species")
        for c in rec.get("careers", []): use(c.get("ref"), "Career")
        for a in self.ledger:
            if a.get("talent"): use(a["talent"], "Talent", int(a.get("times", 1)), a.get("specialisation"))
            elif a.get("skill") and self.lib.current(a["skill"]) not in refs: use(a["skill"], "Skill")
        for x in rec.get("spells", []) + [t for t in rec.get("trappings", []) if t.get("ref")]:
            if self.lib.current(x["ref"]) not in refs: use(x["ref"], "Entry")
        for ref, (e, times) in list(refs.items()):
            for more in self.lib.added_by(ref):
                if more not in refs:
                    try:
                        refs[more] = (self.lib.entry(more), times)
                    except RefError as x:
                        self.note(f"{more} adds to {ref} but can't be read ({x}), so its formulas aren't used.")
        self._used = refs
        return refs

    def applies(self, to, ref):
        """Is a formula's "applies" about this character? {"species": [refs], "career": [refs],
        "class": [names], "specialisation": [names]}; all the keys given must hold. "specialisation"
        is the one the character took of the entry the formula is on (a talent's chosen benefit). A key the build doesn't know is said and
        the formula is left out, never guessed."""
        if not to: return True
        mine = {"species": {self.lib.current((self.rec.get("species") or {}).get("ref") or "")},
                "career": {self.lib.current(c.get("ref") or "") for c in self.rec.get("careers", [])[-1:]}}
        for k, want in to.items():
            want = want if isinstance(want, list) else [want]
            if k in mine:
                if not mine[k] & {self.lib.current(w) for w in want}: return False
            elif k == "specialisation":
                self.used()
                if not self.specs.get(ref, set()) & {norm(w) for w in want}: return False
            elif k == "class":
                cur = self.rec.get("careers", [])[-1:]
                _, ce = self.entry(cur[0].get("ref"), "Career") if cur else (None, None)
                if norm((ce or {}).get("fields", {}).get("class") or "") not in [norm(w) for w in want]: return False
            else:
                self.note(f"{ref}: a formula applies by '{k}', which the build doesn't know, so it isn't used. Read the entry.")
                return False
        return True

    def entry_effects(self):
        """The effects written on the entries the character uses: [{on, add, from, times, at}]."""
        if hasattr(self, "_effects"): return self._effects
        out = []
        for ref, (e, times) in self.used().items():
            for f in e.get("fields", {}).get("effects", []):
                if f.get("on") not in TARGETS:
                    self.note(f"{ref}: an effect on '{f.get('on')}', which isn't a number the sheet has, so it isn't applied. Read the entry.")
                elif (f["on"] in SCALED) != ("multiply" in f):
                    self.note(f"{ref}: an effect on {f['on']} must " + ("multiply" if f["on"] in SCALED else "add") +
                              ", so it isn't applied. Read the entry.")
                elif self.applies(f.get("applies"), ref):
                    out.append({"on": f["on"], "add": f.get("add", 0), "from": ref, "times": times, "at": f.get("at"),
                                **({"multiply": f["multiply"]} if "multiply" in f else {})})
        for row in self.rows():
            for f in row["formulas"].get("effects", []):
                if f.get("on") not in TARGETS:
                    self.note(f"{row['from']}: an effect on '{f.get('on')}', which isn't a number the sheet has, so it isn't applied. Read the row.")
                elif self.applies(f.get("applies"), row["from"]):
                    out.append({"on": f["on"], "add": f.get("add", 0), "from": row["from"], "times": 1})
        self._effects = out
        return out

    def rows(self):
        """The table rows the record names under psychology and mutations ({table, row, from}: a
        mutation rolled, a trait a talent gives by a table): [{list, name, table, cells, from, why,
        formulas}], with the formulas the table's entry carries for that row."""
        if hasattr(self, "_rows"): return self._rows
        out = []
        for key in ("psychology", "mutations"):
            for x in self.rec.get(key) or []:
                if not isinstance(x, dict): continue
                ref, e = self.entry(x.get("table"), key.title())
                if not e: continue
                want = norm(x.get("row") or "")
                hits = [r for b in e.get("content", []) if b.get("type") == "table" for r in b.get("rows", [])
                        if want in [norm(str(c)) for c in r]]
                if len(hits) != 1:
                    self.differ(f"row:{ref.split('/')[-1]}/{slug(x.get('row'))}",
                                f"{key.title()}: '{x.get('row')}' names {len(hits)} rows of {e['name']}; it must name one.", ref)
                    continue
                name = next(str(c) for c in hits[0] if norm(str(c)) == want)
                formulas = next((v for k, v in (e.get("fields", {}).get("rows") or {}).items() if norm(k) == want), None)
                if formulas is None:
                    self.note(f"{name} ({e['name']}): the row carries no formula, so nothing it does to a number is "
                              f"applied. Read the row, and write any effect in the record.")
                out.append({"list": key, "name": name, "table": ref, "cells": [str(c) for c in hits[0] if norm(str(c)) != want and not ROLL.match(str(c).strip())],
                            "from": f"{ref}#{name}", "why": x.get("from"), "formulas": formulas or {},
                            "cite": self.cite(ref), **({"notes": x["notes"]} if x.get("notes") else {})})
        self._rows = out
        return out

    def effects(self, on):
        """What rules do to one number: the effects on the entries used, then the record's own
        ({on, add, from}), for one-off cases. A record line that repeats an entry's effect is
        left out and said, so nothing is counted twice."""
        mine = [e for e in self.entry_effects() if e["on"] == on]
        for e in self.rec.get("effects", []):
            if e.get("on") != on: continue
            src = self.lib.current(e["from"]) if "/" in str(e.get("from", "")) else e.get("from")
            if any(x["from"] == src for x in mine):
                self.note(f"The record's effect on {on} from {e.get('from')} repeats the one on that entry: "
                          f"the entry's is used, and the record's line can be removed.")
                continue
            mine.append(dict(e, times=self.used().get(src, (None, 1))[1]))
        return mine

    def scale(self, on):
        """What the effects on a scaled number multiply it by, and where each comes from."""
        by, parts = 1, []
        for e in self.entry_effects():
            if e["on"] == on and isinstance(e.get("multiply"), (int, float)):
                by *= e["multiply"]
                part = {"on": on, "multiply": e["multiply"], "from": e["from"], **({"at": e["at"]} if e.get("at") is not None else {})}
                parts.append(part)
                if part not in self.applied: self.applied.append(part)
        return by, parts

    def add_effects(self, on, base):
        total, parts = base, []
        for e in self.effects(on):
            names = dict(getattr(self, "names", {}))
            names["times"] = e.get("times", 1)
            try:
                v = Sums(names).value(e.get("add", 0))
            except (ValueError, SyntaxError) as x:
                self.note(f"Effect on {on} from {e.get('from')}: can't work out '{e.get('add')}' ({x}).")
                continue
            total += v
            part = {"on": on, "add": v, "from": e.get("from"), **({"at": e["at"]} if e.get("at") is not None else {})}
            parts.append(part)
            if part not in self.applied: self.applied.append(part)
        return total, parts

    def characteristics(self):
        ch = self.rec.get("characteristics") or {}
        init = ch.get("initial", {})
        formulas = self.sp_fields.get("characteristics", {})
        bought = {c: 0 for c in CHARS}
        for a in self.ledger:
            if a.get("characteristic") in bought: bought[a["characteristic"]] += int(a.get("count", 0))
        out = {}
        for c in CHARS:
            if c not in init:
                self.differ(f"initial:{c}", f"No starting {CHAR_NAME[c]} in the record.")
            base = int(init.get(c, 0))
            start, parts = self.add_effects(c, base)
            rng = dice_range(formulas.get(c, ""))
            if c in init and rng and not rng[0] <= base <= rng[1]:
                self.differ(f"initial:{c}", f"Starting {CHAR_NAME[c]} {base}: the species' {formulas[c]} gives "
                            f"{rng[0]} to {rng[1]}.", self.rec["species"].get("ref"))
            cur = start + bought[c]
            out[c] = {"initial": start, "advances": bought[c], "current": cur, "bonus": cur // 10}
            if parts: out[c]["rolled"], out[c]["effects"] = base, parts
        return out

    def attributes(self):
        f, out = self.sp_fields, {}
        base, parts = self.add_effects("movement", int(f.get("movement", 0) or 0))
        mv = {"base": base, "walk": None, "run": None}
        t = self.table(MOVEMENT)
        if t:
            row = next((r for r in t["rows"] if str(r[0]).strip() == str(base)), None)
            if row: mv["walk"], mv["run"] = int(row[1]), int(row[2])
            else: self.note(f"The Movement table has no row for Movement {base}, so Walk and Run aren't worked out.")
        out["movement"] = mv
        formula = f.get("wounds")
        w = None
        if formula:
            try:
                w = Sums(self.names).value(formula)
            except (ValueError, SyntaxError) as x:
                self.note(f"Wounds: can't work out the species' '{formula}' ({x}).")
        else:
            self.note("The species entry has no Wounds formula, so Wounds aren't worked out.")
        if w is not None: w, _ = self.add_effects("wounds", w)
        st = self.rec.get("state", {})
        out["wounds"] = {"max": w, "formula": formula, "taken": st.get("wounds_taken", 0)}
        extra = self.rec.get("extra_points") or {}
        allowed = int(f.get("extra_points", 0) or 0)
        if sum(int(v) for v in extra.values()) != allowed:
            self.differ("extra-points", f"The species gives {allowed} extra points to share between Fate and "
                        f"Resilience; the record shares out {sum(int(v) for v in extra.values())}.",
                        self.rec.get("species", {}).get("ref"))
        fate, _ = self.add_effects("fate", int(f.get("fate", 0) or 0) + int(extra.get("fate", 0)))
        res, _ = self.add_effects("resilience", int(f.get("resilience", 0) or 0) + int(extra.get("resilience", 0)))
        out["fate"] = {"fate": fate, "fortune": fate - st.get("fortune_spent", 0)}
        out["resilience"] = {"resilience": res, "resolve": res - st.get("resolve_spent", 0),
                             "motivation": self.rec.get("motivation")}
        limit, _ = self.add_effects("corruption", self.names["TB"] + self.names["WPB"])
        out["corruption"] = {"points": st.get("corruption", 0), "threshold": limit, "rule": RULE["corruption"]}
        return out

    def talent_max(self, text):
        """A talent's Max as a number: "1", "Initiative Bonus", "Intelligence Bonus + Willpower Bonus".
        None when there is no limit or it isn't a sum of those."""
        if text is None or norm(str(text)) in ("none", ""): return None
        total = 0
        for part in str(text).split("+"):
            p = part.strip()
            if p.isdigit(): total += int(p); continue
            m = re.fullmatch(r"(.+?)\s+bonus", p, re.I)
            c = NAME_CHAR.get(norm(m.group(1))) if m else None
            if not c: return None
            total += self.names[c + "B"]
        return total

    def talents(self):
        got = {}
        for i, a in enumerate(self.ledger):
            if not a.get("talent"): continue
            ref, e = self.entry(a["talent"], "Talent")
            key = (ref, a.get("specialisation"))
            g = got.setdefault(key, {"ref": ref, "entry": e, "spec": a.get("specialisation"), "times": 0, "how": []})
            g["times"] += int(a.get("times", 1)); g["how"].append(a.get("how"))
        out = []
        for (ref, spec), g in got.items():
            e = g["entry"] or {}
            f = e.get("fields", {})
            name = e.get("name", ref) + (f" ({spec})" if spec else "")
            mx = self.talent_max(f.get("max"))
            if e and "max" not in f:
                self.note(f"{name}: the entry gives no Max, so how often it can be taken isn't checked.")
            elif f.get("max") is not None and mx is None and norm(str(f["max"])) != "none":
                self.note(f"{name}: Max is '{f['max']}', which the build can't turn into a number.")
            if mx is not None and g["times"] > mx:
                self.differ(f"talent-max:{ref.split('/')[-1]}" + (f"/{slug(spec)}" if spec else ""),
                            f"{name} taken {g['times']} times; its Max is {f['max']} ({mx}).", ref)
            cat = ref.split("/")[0]
            listed = self.from_species(cat, ref, spec) or bool(self.in_career(cat, ref, spec))
            if e and not listed and set(g["how"]) - {"free"}:
                self.differ(f"talent-source:{ref.split('/')[-1]}" + (f"/{slug(spec)}" if spec else ""),
                            f"{name} isn't among the species' talents or those of a career level reached.",
                            RULE["non-career"])
            out.append({"name": name, "ref": ref, "times": g["times"], "max": mx, "max_text": f.get("max"),
                        "tests": f.get("tests"), "cite": self.cite(ref) if e else "",
                        **({"added_by": self.lib.added_by(ref)} if self.lib.added_by(ref) else {})})
        self.choose_one(got)
        return sorted(out, key=lambda t: t["name"])

    def choose_one(self, got):
        """A species list's "X or Y" gives one of them."""
        sp = self.lists()["species"]
        for x in sp["talents"]:
            if not isinstance(x, dict): continue
            have = []
            for name in x.get("choose_one", []):
                for (ref, spec), g in got.items():
                    if ref.startswith("talents/") and self.offered("talents", name, ref, spec) and \
                            not self.in_career("talents", ref, spec) and name not in have:
                        have.append(name)
            if len(have) > 1:
                self.differ("species-choice:" + "+".join(slug(h) for h in have),
                            f"The species gives one of {' or '.join(x['choose_one'])}; the character has "
                            f"{' and '.join(have)}, and no career level reached lists them.", sp["from"])

    def skills(self):
        adv = {}
        for a in self.ledger:
            if not a.get("skill"): continue
            ref, e = self.entry(a["skill"], "Skill")
            k = (ref, a.get("specialisation"))
            adv.setdefault(k, {"entry": e, "count": 0})["count"] += int(a.get("count", 0))
        rows = {}
        for _, r in self.lib.index("skills"):          # every basic skill, taken or not
            if r.get("advanced") is False:
                rows[(f"skills/{r['slug']}", None)] = r
        for (ref, spec), g in adv.items():
            e = g["entry"]
            if not e: continue
            f = e.get("fields", {})
            if f.get("grouped") and not spec:
                self.differ(f"skill-specialisation:{ref.split('/')[-1]}",
                            f"{e['name']} is a grouped skill: the record must say which specialisation.", ref)
            if "advanced" not in f:
                self.note(f"{e['name']}: the entry doesn't say whether it is basic or advanced; shown as advanced.")
            rows[(ref, spec)] = {"name": e["name"], **f}
        # a career skill the career settles (an exact name, or the one specialisation chosen for it) is
        # on the sheet even before any advances are taken in it
        for sl in self.skill_slots():
            ref, spec = (sl["choice"] or (None, None)) if sl["kind"] == "one" else \
                (sl["ref"], self.lib.named("skills", sl["listed"])[1]) if sl["kind"] == "exact" else (None, None)
            if not ref or not spec or any(r == ref and sp and norm(sp) == norm(spec) for r, sp in rows): continue
            e = self.lib.entry(ref)
            if e: rows[(ref, spec)] = {"name": e["name"], **e.get("fields", {})}
        basic, advanced = [], []
        for (ref, spec), f in rows.items():
            c = f.get("characteristic")
            n = adv.get((ref, spec), {}).get("count", 0)
            if c not in CHARS:
                self.note(f"{f['name']}: no characteristic in the entry, so its total isn't worked out.")
            row = {"name": f["name"] + (f" ({spec})" if spec else ""), "ref": ref, "characteristic": c,
                   "advances": n, "total": (self.names[c] + n) if c in CHARS else None,
                   "career": bool(self.in_career("skills", ref, spec))}
            (basic if f.get("advanced") is False else advanced).append(row)
        return {"basic": sorted(basic, key=lambda r: r["name"]), "advanced": sorted(advanced, key=lambda r: r["name"])}

    def resolve(self, text):
        """"Willpower Bonus yards" -> "7 yards", with this character's numbers."""
        if not isinstance(text, str): return text
        def sub(m):
            c = NAME_CHAR[norm(m.group(1))]
            return str(self.names[c + "B"] if m.group(2) else self.names[c])
        return re.sub(r"\b(%s)(\s+Bonus)?\b" % "|".join(CHAR_NAME.values()), sub, text)

    def spell_price(self, kind, known):
        """The price of a new spell of this kind when `known` are known already, from the table in the
        talent that teaches it ("Up to Willpower Bonus × 2: 100 XP ... and so on"), times whatever the
        character's rules multiply spell prices by. None, with a note, when it can't be read."""
        talent, title = SPELL_COSTS[kind]
        ref = self.lib.find("talents", talent)
        t = self.table((self.lib.current(ref), title)) if ref else None
        if not t:
            if not ref: self.note(f"The {talent} talent isn't in the library, so its spells aren't priced.")
            return None
        rows = []
        for r in t["rows"]:
            m = re.match(r"\s*Up to (.+?) Bonus\s*[×x]\s*(\d+)", str(r[0]))
            p = re.match(r"\s*(\d+)", str(r[1]))
            c = NAME_CHAR.get(norm(m.group(1))) if m else None
            if not (c and p):
                self.note(f"The '{title}' table has a row the build can't read ({r[0]}: {r[1]}), so those spells aren't priced.")
                return None
            rows.append((c, int(m.group(2)), int(p.group(1))))
        bonus = self.names[rows[0][0] + "B"]
        if bonus < 1:
            self.note(f"With a {CHAR_NAME[rows[0][0]]} Bonus of {bonus} the '{title}' table gives no price.")
            return None
        band = max(1, -(-known // bonus))                       # known 1..B: the first row; B+1..2B: the second
        prices = {k: p for _, k, p in rows}
        top = max(prices)
        step = prices[top] - prices.get(top - 1, 0)             # "...and so on"
        price = prices.get(band, prices[top] + step * (band - top))
        by, _ = self.scale("spell_cost")
        return int(-(-price * by // 1))                         # a part of an XP is rounded up

    def spells(self, talents):
        out, self.spell_purchases, self.spells_unpriced = [], [], False
        lores = {norm(t["name"]) for t in talents}
        mine = [w for w in list(WINDS) + list(WINDS.values()) if any(n.startswith("arcane magic") and w in n for n in lores)]
        known, free = {}, 0
        for i, s in enumerate(self.rec.get("spells", [])):
            ref, e = self.entry(s.get("ref"), "Spell")
            if not e: continue
            f = e.get("fields", {})
            kind, lore = f.get("kind"), f.get("lore")
            if kind == "petty" and not any(n.startswith("petty magic") for n in lores):
                self.differ(f"spell-talent:{ref.split('/')[-1]}", f"{e['name']} is a petty spell; the character has no Petty Magic talent.", ref)
            if kind == "lore" and lore:
                want = {norm(lore)} | {w for w, l in WINDS.items() if l == norm(lore)}
                if not any(n.startswith("arcane magic") and any(w in n for w in want) for n in lores):
                    self.differ(f"spell-lore:{ref.split('/')[-1]}",
                                f"{e['name']} is from the Lore of {lore}; the character has no Arcane Magic talent for it.", ref)
            out.append({"name": e["name"], "ref": ref, "kind": kind, "lore": lore, "cn": f.get("cn"),
                        "range": self.resolve(f.get("range")), "target": self.resolve(f.get("target")),
                        "duration": self.resolve(f.get("duration")), "cite": self.cite(ref)})
            # what it cost: spells are counted per talent that teaches them, in the order learned
            how = s.get("how")
            if how not in SPELL_HOW:
                self.differ(f"spell-how:{ref.split('/')[-1]}", f"{e['name']}: the record must say how it was learned "
                            f"({', '.join(SPELL_HOW)}).")
                how = "imported"
            group = "petty" if kind == "petty" else norm(s.get("lore") or lore or (mine[0] if mine else "")) if kind in ("lore", "arcane") else None
            if kind == "arcane" and not s.get("lore") and len({WINDS.get(w, w) for w in mine}) > 1:
                self.note(f"{e['name']} is an Arcane spell and the character has more than one lore: write the lore it was "
                          f"learned under on its line in the record. Counted under the first.")
            before = known.get(group, 0)
            if group is not None: known[group] = before + 1
            if how == "imported":
                self.spells_unpriced = True
            elif how == "talent":
                free += 1
                if kind != "petty":
                    self.differ(f"spell-free:{ref.split('/')[-1]}", f"{e['name']} is recorded as coming with a talent; only "
                                f"Petty Magic gives spells that way.", ref)
            elif how == "xp":
                cost = self.spell_price(kind, before) if kind in SPELL_COSTS else None
                if kind not in SPELL_COSTS:
                    self.note(f"{e['name']} is a {kind}: the build has no price for those. Read how it is learned.")
                if s.get("xp") is not None and cost is not None and s["xp"] != cost:
                    self.differ(f"xp-cost:spell-{ref.split('/')[-1]}", f"{e['name']} cost {s['xp']} XP in the record; the rules make it {cost}.", ref)
                self.spell_purchases.append({"spell": e["name"], "xp": s.get("xp", cost), "by_the_rules": cost})
        if free > self.names["WPB"]:
            self.differ("petty-free", f"{free} petty spells are recorded as coming with Petty Magic; it gives as many as the "
                        f"Willpower Bonus ({self.names['WPB']}).", self.lib.find("talents", "Petty Magic"))
        self.spells_known = known
        if self.spells_unpriced:
            self.note("Some spells were imported from a sheet without their history, so the XP they cost isn't worked out.")
        return out

    def trappings(self):
        lines, ids = [], {}
        for t in self.rec.get("trappings", []):
            if t.get("id"): ids[t["id"]] = t
        armour = {loc: 0 for loc in LOCATIONS}
        carried = 0
        for t in self.rec.get("trappings", []):
            e, ref = None, None
            if t.get("ref"):
                ref, e = self.entry(t["ref"], "Trapping")
            f = (e or {}).get("fields", {})
            name = t.get("name") or (e or {}).get("name") or t.get("ref")
            qty = int(t.get("qty", 1))
            enc = t.get("enc", f.get("enc"))
            try:
                enc = int(str(enc).strip()) if enc not in (None, "", "–", "-") else 0
            except ValueError:
                self.note(f"{name}: Encumbrance '{enc}' isn't a number; counted as 0.")
                enc = 0
            depth, up, seen = 0, t.get("in"), set()
            while up and up in ids and up not in seen:
                seen.add(up); depth += 1; up = ids[up].get("in")
            if t.get("in") and t["in"] not in ids:
                self.differ(f"trapping-in:{t['in']}", f"{name} is in '{t['in']}', which no trapping has as its id.")
            counted = enc * qty
            if t.get("worn"): counted = max(0, enc - 1) * qty            # Worn Items
            if depth: counted = 0                                        # only the container's own Enc counts
            if t.get("stowed"): counted = 0                              # left behind, on a mount or cart
            carried += counted
            line = {"name": name, "qty": qty, "enc": enc, "counts": counted, "depth": depth,
                    **({"ref": ref, "cite": self.cite(ref)} if e else {}),
                    **({k: t[k] for k in ("worn", "stowed", "notes") if t.get(k)})}
            if f.get("kind") in ("melee", "ranged"):
                w = {"group": f.get("group"), "qualities": f.get("qualities", [])}
                if f.get("reach"): w["reach"] = f["reach"]
                if f.get("range"): w["range"] = self.resolve(str(f["range"]))
                dmg = f.get("damage")
                if dmg:
                    try:
                        w["damage"] = Sums(self.names).value(str(dmg).lstrip("+"))
                    except (ValueError, SyntaxError):
                        w["damage"] = None
                    w["damage_text"] = dmg
                line["weapon"] = w
            if f.get("kind") == "armour" and t.get("worn"):
                locs = f.get("locations") or []
                locs = split_list(locs) if isinstance(locs, str) else locs
                try:
                    ap = int(str(f.get("armour_points", 0)).strip())
                except ValueError:
                    ap = 0
                    self.note(f"{name}: Armour Points '{f.get('armour_points')}' isn't a number; not added to the locations.")
                for loc in locs:
                    hit = [L for L in LOCATIONS if norm(loc) in (norm(L), "all", norm(L).split()[-1] + "s", norm(L).split()[-1])]
                    if not hit: self.note(f"{name}: location '{loc}' isn't one the sheet knows; its Armour Points aren't added.")
                    for L in hit: armour[L] += ap
                line["armour"] = {"ap": ap, "locations": locs}
            lines.append(line)
        limit, _ = self.add_effects("encumbrance", self.names["SB"] + self.names["TB"])
        return lines, armour, {"carried": carried, "max": limit, "rule": RULE["encumbrance"]}

    # ------------------------------------------------------------------ XP
    def cost_rows(self):
        t = self.table(COSTS)
        if not t: return None
        rows = []
        for r in t["rows"]:
            m = re.match(r"\s*(\d+)\s*(?:to|[-–])\s*(\d+)", str(r[0]))
            if m: rows.append((int(m.group(1)), int(m.group(2)), int(r[1]), int(r[2])))
        return rows

    def step_cost(self, rows, already, col):
        """One advance when `already` have been taken: the table's bands are "0 to 5", "6 to 10" by the
        number the advance brings you to, so the first five cost the first row."""
        to = already + 1
        for lo, hi, ch, sk in rows:
            if max(lo, 1) <= to <= hi: return ch if col == "characteristic" else sk
        return None

    def xp(self):
        x = self.rec.get("xp") or {}
        rows = self.cost_rows()
        spent, lines, taken, unknown = 0, [], {}, False
        if any(a.get("how") == "imported" for a in self.ledger):
            self.note("Some advances were imported from a sheet without their history, so the XP they cost "
                      "isn't worked out; XP spent is what the record says.")
            unknown = True
        for i, a in enumerate(self.ledger):
            kind = next((k for k in ("characteristic", "skill", "talent", "career") if a.get(k)), None)
            key = (kind, self.lib.current(a[kind]) if kind in ("skill", "talent") else a.get(kind), a.get("specialisation"))
            n = int(a.get("count", a.get("times", 1)))
            before = taken.get(key, 0)
            taken[key] = before + n
            if a.get("how") != "xp": continue
            cost = None
            if kind in ("characteristic", "skill") and rows:
                if kind == "skill":
                    home = bool(self.in_career("skills", key[1], key[2]))
                else:
                    home = any(a["characteristic"] in f.get("characteristics", []) for _, _, f in self.lists()["levels"])
                steps = [self.step_cost(rows, before + j, kind) for j in range(n)]
                if None in steps:
                    self.note(f"Advance {i + 1}: the cost table doesn't go as far as {before + n} advances.")
                else:
                    cost = sum(steps) * (1 if home else 2)
                    if not home:
                        self.note(f"Advance {i + 1} ({a[kind]}{' (' + a['specialisation'] + ')' if a.get('specialisation') else ''}) "
                                  f"isn't in the career, so it costs double {self.cite(RULE['non-career'])}.")
            elif kind == "talent":
                rising = self.setting("talent_cost") == "rising"
                cost = sum(100 + (100 * (before + j) if rising else 0) for j in range(n))      # Talent Advances
                level = self.current_level if self.setting("talents_from") == "current-level" else None
                if not self.in_career("talents", key[1], key[2], level):
                    self.note(f"Advance {i + 1}: {a['talent']} isn't a talent of " + ("the current career level; the "
                              "rules sell talents only from the level you are in." if level else "any career level reached."))
            elif kind == "career":
                cost = a.get("xp")
                if cost is None: self.note(f"Advance {i + 1}: a career change needs its XP written in the record (100 or 200, +100 for a new class).")
            if a.get("xp") is not None and cost is not None and a["xp"] != cost:
                self.differ(f"xp-cost:{i}", f"Advance {i + 1} cost {a['xp']} XP in the record; the rules make it {cost}.",
                            RULE["non-career"] if kind != "talent" else RULE["talents"])
            paid = a.get("xp", cost)
            if paid is None: unknown = True
            else: spent += paid
            lines.append({"advance": i + 1, "xp": paid, "by_the_rules": cost})
        for sp in getattr(self, "spell_purchases", []):
            if sp["xp"] is None: unknown = True
            else: spent += sp["xp"]
            lines.append(sp)
        if getattr(self, "spells_unpriced", False): unknown = True
        total = x.get("total")
        said = x.get("spent")
        at_creation = self.creation_xp()
        out = {"total": total, "spent": said if said is not None else spent,
               "current": None, "worked_out": None if unknown else spent, "purchases": lines, "at_creation": at_creation}
        if said is not None and not unknown and said != spent:
            self.differ("xp-spent", f"The record says {said} XP spent; its purchases add up to {spent}.")
        if total is not None and out["spent"] is not None:
            out["current"] = total - out["spent"]
            if out["current"] < 0:
                self.differ("xp-overspent", f"{out['spent']} XP spent of {total} earned: {-out['current']} more than the character has.")
        return out

    def grants(self):
        """[(rule ref, entry, grant)] from the creation rules in play and what adds to them."""
        out = []
        for rule in CREATION_RULES:
            refs = [self.lib.current(rule)]
            refs += [r for r in self.lib.added_by(refs[0]) if r not in refs]
            for ref in refs:
                try: e = self.lib.entry(ref)
                except RefError: continue
                out += [(ref, e, g) for g in e.get("fields", {}).get("grants", [])]
        return out

    def granted_from(self, src, kind, line):
        """Is this advance line's skill, talent or characteristic one the grant's list offers?"""
        if src == "species":
            return kind != "characteristic" and self.from_species(kind + "s", self.lib.current(line[kind]), line.get("specialisation"))
        first = next(((cref, f) for cref, n, f in self.lists()["levels"] if n == 1), None)
        if not first: return False
        f = first[1]
        if kind == "characteristic": return line["characteristic"] in f.get("characteristics", [])
        if kind == "skill":
            return any(sl["career"] == first[0] and sl["level"] == 1 and
                       self.slot_covers(sl, self.lib.current(line["skill"]), line.get("specialisation")) for sl in self.skill_slots())
        return any(self.offered("talents", x, self.lib.current(line["talent"]), line.get("specialisation")) for x in f.get("talents", []))

    def creation(self):
        """Check the advances gained at creation (`how`: species or career) against what the creation
        rules grant. A grant: {id, how, kind (skill|talent|characteristic), from (species |
        first-career-level), and what it gives: "picks" [{count, advances}] (so many at so many),
        "total" with "most" (advances to share out, at most so many in one), or "count" (so many
        taken), "at"}. Returns [{rule, id, cite, kind, how, given, left}] for the options report."""
        lines = [a for a in self.ledger if a.get("how") in ("species", "career")]
        grants = self.grants()
        out = []
        if lines and not grants:
            self.note("The creation rules carry no grants yet, so what the species and career gave at creation isn't checked. Read them.")
            return out
        covered = set()
        for ref, e, g in grants:
            how, kind, src, gid = g.get("how"), g.get("kind"), g.get("from"), f"creation:{ref.split('/')[-1]}/{g.get('id')}"
            if kind not in ("skill", "talent", "characteristic") or src not in GRANT_FROM or how not in ("species", "career"):
                self.note(f"{e['name']}: grant {g.get('id')} has a word the build doesn't know ({how}, {kind}, {src}); not checked.")
                continue
            covered.add((how, kind))
            mine = [a for a in lines if a["how"] == how and a.get(kind)]
            per = {}
            for a in mine:
                if not self.granted_from(src, kind, a):
                    try: base = a[kind] if kind == "characteristic" else self.lib.entry(self.lib.current(a[kind]))["name"]
                    except RefError: base = a[kind]
                    name = base + (f" ({a['specialisation']})" if a.get("specialisation") else "")
                    self.differ(f"{gid}:{slug(name)}", f"{name} is recorded as gained from the {how} at creation; "
                                f"{'the species' if src == 'species' else 'the first career level'} doesn't offer it.", ref)
                k = (self.lib.current(a[kind]) if kind != "characteristic" else a[kind], norm(a.get("specialisation") or ""))
                per[k] = per.get(k, 0) + int(a.get("count", a.get("times", 1)))
            row = {"rule": ref, "id": g.get("id"), "cite": self.cite(ref), "kind": kind, "how": how, "from": src}
            if "picks" in g:
                want = {int(p["advances"]): int(p["count"]) for p in g["picks"]}
                have = {}
                for v in per.values(): have[v] = have.get(v, 0) + 1
                bad = {v: n for v, n in have.items() if n > want.get(v, 0)}
                if bad:
                    self.differ(gid, f"{e['name']} gives " + ", ".join(f"{n} at {v}" for v, n in want.items()) +
                                f"; the record has " + ", ".join(f"{n} at {v}" for v, n in sorted(have.items(), reverse=True)) + ".", ref)
                row["given"], row["left"] = have, {v: n - have.get(v, 0) for v, n in want.items() if n > have.get(v, 0)}
            elif "total" in g:
                total, most = int(g["total"]), int(g.get("most", g["total"]))
                spent = sum(per.values())
                over = [k for k, v in per.items() if v > most]
                if spent > total or over:
                    self.differ(gid, f"{e['name']} gives {total} advances" + (f", at most {most} in one" if most < total else "") +
                                f"; the record has {spent}" +
                                (f", with more than {most} in {len(over)}" if over else "") + ".", ref)
                row["given"], row["left"] = spent, max(0, total - spent)
            elif "count" in g:
                n = sum(per.values())
                if n > int(g["count"]):
                    self.differ(gid, f"{e['name']} gives {g['count']} {kind}(s); the record has {n}.", ref)
                row["given"], row["left"] = n, max(0, int(g["count"]) - n)
            else:
                row["given"], row["left"] = sum(per.values()), None        # only where they come from is checked
            out.append(row)
        for how, kind in sorted({(a["how"], next(k for k in ("skill", "talent", "characteristic") if a.get(k)))
                                 for a in lines if any(a.get(k) for k in ("skill", "talent", "characteristic"))} - covered):
            self.differ(f"creation:{how}-{kind}", f"The record has {kind}s gained from the {how} at creation, and no creation rule grants any.")
        return out

    def creation_xp(self):
        """The XP the creation steps gave, by how the record says each was settled: each step's rule
        carries the amounts as "xp" effects, narrowed with "applies": {"how": [...]}. {"xp": total or
        None when a step's share can't be worked out, "steps": [{step, how, xp, cite}]}."""
        rec, steps, known = self.rec, [], True
        for step, rule, ways in CREATION:
            how = (rec.get("careers") or [{}])[0].get("how") if step == "career" else (rec.get(step) or {}).get("how")
            try:
                ref = self.lib.current(rule); e = self.lib.entry(ref)
            except RefError:
                ref, e = rule, None
            xp = None
            if how in (None, "imported"):
                self.note(f"The record doesn't say how the {step} was settled at creation ({', '.join(ways)}), so the XP it gave isn't worked out.")
            elif how not in ways:
                self.differ(f"creation-how:{step}", f"The {step} was settled '{how}' at creation; the record must say one of: {', '.join(ways)}.")
            elif not e:
                self.note(f"{rule} isn't in the library, so the XP the {step} gave at creation isn't worked out.")
            else:
                fx = [f for f in e.get("fields", {}).get("effects", []) if f.get("on") == "xp"]
                if not fx:
                    self.note(f"{e['name']} has no formula for the XP it gives, so the {step}'s share isn't worked out. Read the rule.")
                else:
                    xp = sum(f.get("add", 0) for f in fx if how in (f.get("applies") or {}).get("how", []))
            if xp is None: known = False
            steps.append({"step": step, "how": how, "xp": xp, "cite": self.cite(ref) if e else None})
        total = sum(s["xp"] for s in steps) if known else None
        said = (rec.get("xp") or {}).get("bonus_at_creation")
        if said is not None and total is not None and said != total:
            self.differ("xp-creation", f"The record says creation gave {said} XP; the rules for how it was settled give {total}.")
        return {"xp": total, "steps": steps}

    def levels_complete(self, m):
        """Each level left behind should have been completed (or 200 XP paid to leave it early). A
        level's characteristics and available skills are its own and those of the levels below it in
        the career; its talent must be one of its own."""
        t = self.table(LEVEL_ADVANCES)
        need = {str(r[0]).strip(): int(r[1]) for r in t["rows"]} if t else {}
        skills = {(r["ref"], r["name"]): r["advances"] for r in m["skills"]["basic"] + m["skills"]["advanced"]}
        for c in self.rec.get("careers", []):
            cref, ce = self.entry(c.get("ref"), "Career")
            if not ce: continue
            adv = ce.get("fields", {}).get("advances", {})
            for n in range(1, int(c.get("level", 1))):
                if n in c.get("left_incomplete", []): continue
                f, want = adv.get(str(n), {}), need.get(str(n))
                if want is None:
                    if t: self.note(f"The Level Advances table has no row for level {n}, so whether {ce['name']} level {n} was completed isn't checked.")
                    continue
                upto = [adv.get(str(k), {}) for k in range(1, n + 1)]
                chars = [x for lv in upto for x in lv.get("characteristics", [])]
                listed_skills = [x for lv in upto for x in lv.get("skills", [])]
                short = [x for x in dict.fromkeys(chars) if m["characteristics"].get(x, {}).get("advances", 0) < want]
                # each skill the character has counts once, under whichever listed name covers it
                mine = [sl for sl in self.skill_slots() if sl["career"] == cref and sl["level"] <= n]
                done = sum(1 for (ref, name), v in skills.items() if v >= want and any(
                    self.slot_covers(sl, ref, (re.search(r"\((.+)\)$", name) or [None, None])[1]) for sl in mine))
                tal = any(self.in_career("talents", tl["ref"], (re.search(r"\((.+)\)$", tl["name"]) or [None, None])[1], (cref, n))
                          for tl in m["talents"])
                why = []
                if short: why.append(f"{', '.join(short)} below {want} advances")
                if done < min(8, len(set(listed_skills))): why.append(f"{done} of its skills at {want} advances (8 needed)")
                if not tal: why.append("no talent from that level")
                if why:
                    self.gaps.append({"career": ce["name"], "level": n, "level_name": ce["fields"]["levels"][n - 1], "missing": why})
                    self.differ(f"level-complete:{cref.split('/')[-1]}/{n}",
                                f"{ce['name']} level {n} ({ce['fields']['levels'][n - 1]}) isn't complete: {'; '.join(why)}. "
                                f"Leaving a level early costs 200 XP instead of 100; write \"left_incomplete\": [{n}] on the career if that was done.",
                                RULE["completing"])

    # ------------------------------------------------------------------ house rules
    def setting(self, key):
        """How the campaign plays one of SETTINGS: the books' way unless a house rule sets another.
        A key or value the build doesn't know is said and not used."""
        if not hasattr(self, "_settings"):
            self._settings, self.set_by = {k: v[0] for k, v in SETTINGS.items()}, {}
            for h in (self.lib.campaign or {}).get("house_rules", []):
                for k, v in (h.get("set", {}) if isinstance(h, dict) else {}).items():
                    if k not in SETTINGS or v not in SETTINGS[k]:
                        self.note(f"House rule '{h.get('id') or h.get('text')}' sets {k} to {v!r}, which the build doesn't know "
                                  f"(it knows {', '.join(f'{a}: {' or '.join(b)}' for a, b in SETTINGS.items())}), so it isn't applied.")
                    else:
                        self._settings[k] = v
                        if v != SETTINGS[k][0]: self.set_by[k] = {"value": v, "house_rule": h.get("id"), "text": h.get("text")}
        return self._settings[key]

    # ------------------------------------------------------------------ settled differences
    def settle(self):
        """Split differences into open ones and those the record or the campaign has accepted."""
        accept = []
        for x in self.rec.get("exceptions", []):
            accept.append((x.get("id", ""), x.get("why", ""), x.get("house_rule")))
        for h in (self.lib.campaign or {}).get("house_rules", []):
            if isinstance(h, dict):
                for pat in h.get("accepts", []): accept.append((pat, h.get("text", ""), h.get("id")))
        opened, accepted, used = [], [], set()
        for d in self.diff:
            hit = next((a for a in accept if fnmatch.fnmatchcase(d["id"], a[0])), None)
            if hit:
                used.add(hit[0])
                accepted.append({**d, "why": hit[1], **({"house_rule": hit[2]} if hit[2] else {})})
            else:
                opened.append(d)
        for x in self.rec.get("exceptions", []):
            if x.get("id") not in used:
                self.note(f"The exception '{x.get('id')}' matches no difference in this build: it may no longer be needed.")
        return opened, accepted


# ---------------------------------------------------------------------------- comparing with a kept sheet
def compare(model, shown):
    """Where a sheet someone kept by hand (read_sheet_export.py's JSON) and the build disagree:
    [{what, shown, built}]. Only what the sheet shows is compared."""
    out = []

    def check(what, s, b):
        if s in (None, ""): return
        if str(s).strip() != str(b).strip() and not (isinstance(b, (int, float)) and _num(s) == b):
            out.append({"what": what, "shown": s, "built": b})

    for c, v in (shown.get("characteristics") or {}).items():
        for k in ("initial", "advances", "current", "bonus"):
            if c in model["characteristics"]: check(f"{CHAR_NAME.get(c, c)} {k}", v.get(k), model["characteristics"][c][k])
    for k in ("base", "walk", "run"):
        check(f"Movement {k}", (shown.get("movement") or {}).get(k), model["movement"][k])
    check("Wounds", shown.get("wounds"), model["wounds"]["max"])
    check("Fate", shown.get("fate"), model["fate"]["fate"])
    check("Resilience", shown.get("resilience"), model["resilience"]["resilience"])
    check("Encumbrance carried", (shown.get("encumbrance") or {}).get("total"), model["encumbrance"]["carried"])
    check("Encumbrance limit", (shown.get("encumbrance") or {}).get("max"), model["encumbrance"]["max"])
    check("Status", shown.get("status"), model["career"].get("status"))
    for k in ("total", "spent", "current"):
        check(f"XP {k}", (shown.get("xp") or {}).get(k), model["xp"][k])
    built = {norm(r["name"]): r for r in model["skills"]["basic"] + model["skills"]["advanced"]}
    for s in shown.get("skills", []):
        b = built.get(norm(s["name"]))
        if not b:
            if s.get("advances") or s.get("advanced"): out.append({"what": f"Skill {s['name']}", "shown": s.get("total"), "built": "not on the built sheet"})
            continue
        check(f"{b['name']} characteristic", s.get("characteristic"), b["characteristic"])
        check(f"{b['name']} advances", s.get("advances"), b["advances"])
        check(f"{b['name']} total", s.get("total"), b["total"])
        if s.get("career") is not None: check(f"{b['name']} career skill", s["career"], b["career"])
    names = {norm(s["name"]) for s in shown.get("skills", [])}
    for r in model["skills"]["basic"]:
        if shown.get("skills") and norm(r["name"]) not in names:
            out.append({"what": f"Skill {r['name']}", "shown": "not on the sheet", "built": r["total"]})
    tb = {norm(t["name"]): t for t in model["talents"]}
    for t in shown.get("talents", []):
        b = tb.get(norm(t["name"]))
        if not b:
            out.append({"what": f"Talent {t['name']}", "shown": t.get("count"), "built": "not on the built sheet"}); continue
        check(f"{b['name']} times taken", t.get("count"), b["times"])
        if b["max"] is not None: check(f"{b['name']} max", t.get("max"), b["max"])
    sb = {norm(s["name"]): s for s in model["spells"]}
    for s in shown.get("spells", []):
        b = sb.get(norm(s["name"]))
        if not b:
            out.append({"what": f"Spell {s['name']}", "shown": "on the sheet", "built": "not on the built sheet"}); continue
        for k in ("cn", "range", "target", "duration"):
            check(f"{b['name']} {k}", _short(s.get(k)), _short(b.get(k)))
    return out


def _num(s):
    try:
        return float(str(s).strip())
    except ValueError:
        return None


def _short(v):
    """"70 yds" and "70 yards" are the same thing to a reader."""
    if v is None: return None
    return re.sub(r"\byards?\b", "yds", str(v).strip(), flags=re.I).lower()


# ---------------------------------------------------------------------------- the readable sheet
def markdown(m):
    L = []
    c = m.get("career") or {}
    L.append(f"# {m.get('name') or m.get('slug')}")
    sp = m["species"]
    L.append(f"{sp.get('name') or '?'}{' (' + sp['origin'] + ')' if sp.get('origin') else ''} · "
             f"{c.get('class') or '?'} · {c.get('name') or '?'} {c.get('level', '')}: {c.get('level_name') or '?'} · "
             f"Status {c.get('status') or '?'}")
    if c.get("path"):
        L.append("Career path: " + "; ".join(f"{p['class']}: {p['name']} ({', '.join(p['levels'])})" for p in c["path"]))
    for g in c.get("to_complete", []):
        L.append(f"Still to complete in {g['career']} {g['level']} ({g['level_name']}): {'; '.join(g['missing'])}")
    for title, key in (("To settle", "incomplete"),):
        if m.get(key):
            L += ["", f"## {title}"] + [f"- {x if isinstance(x, str) else x.get('what')}" for x in m[key]]
    if m["differences"]:
        L += ["", "## Differs from the rules"] + [f"- {d['text']} `{d['id']}`" for d in m["differences"]]
    L += ["", "## Characteristics", "| | " + " | ".join(CHARS) + " |", "|---" * 11 + "|"]
    for k in ("initial", "advances", "current", "bonus"):
        L.append(f"| {k.title()} | " + " | ".join(str(m["characteristics"][x][k]) for x in CHARS) + " |")
    mv, w = m["movement"], m["wounds"]
    L += ["", f"Movement {mv['base']} (Walk {mv['walk']}, Run {mv['run']}) · Wounds {w['max']} ({w['formula']}), {w['taken']} taken · "
              f"Fate {m['fate']['fate']} / Fortune {m['fate']['fortune']} · Resilience {m['resilience']['resilience']} / "
              f"Resolve {m['resilience']['resolve']} · Corruption {m['corruption']['points']} of {m['corruption']['threshold']} · "
              f"Encumbrance {m['encumbrance']['carried']} of {m['encumbrance']['max']}"]
    x = m["xp"]
    L.append(f"XP: {x['current']} current, {x['spent']} spent, {x['total']} total")
    c = x.get("at_creation") or {}
    if c.get("steps"):
        L.append(f"Of the total, from creation: {c['xp'] if c['xp'] is not None else 'not worked out'}" +
                 (" (" + "; ".join(f"{s['step']} {s['how'] or 'not said'}: " + (f"{s['xp']} XP" if s["xp"] is not None else "?") +
                                   (f" {s['cite']}" if s["cite"] else "") for s in c["steps"]) + ")"))
    for k, h in (m.get("house_rules") or {}).items():
        L.append(f"House rule: {h.get('text') or h.get('house_rule')} ({k.replace('_', ' ')}: {h['value']})")
    if any(m["armour"].values()):
        L.append("Armour: " + ", ".join(f"{k} {v}" for k, v in m["armour"].items()))
    for title, rows in (("Basic skills", m["skills"]["basic"]), ("Advanced skills", m["skills"]["advanced"])):
        L += ["", f"## {title}", "| Skill | Career | Char. | Adv | Total |", "|---|---|---|---|---|"]
        L += [f"| {r['name']} | {'✓' if r['career'] else ''} | {r['characteristic']} | {r['advances']} | {r['total']} |" for r in rows]
    L += ["", "## Talents", "| Talent | Taken | Max | Tests | |", "|---|---|---|---|---|"]
    L += [f"| {t['name']} | {t['times']} | {t['max'] if t['max'] is not None else '–'} | {t['tests'] or ''} | {t['cite']} |" for t in m["talents"]]
    if m["spells"]:
        L += ["", "## Spells", "| Spell | Lore | CN | Range | Target | Duration | |", "|---|---|---|---|---|---|---|"]
        L += [f"| {s['name']} | {s['lore'] or s['kind']} | {s['cn']} | {s['range']} | {s['target']} | {s['duration']} | {s['cite']} |" for s in m["spells"]]
    if m["trappings"]:
        L += ["", "## Trappings", "| Trapping | Qty | Enc | Counts | Details |", "|---|---|---|---|---|"]
        for t in m["trappings"]:
            d = []
            if t.get("weapon"):
                wp = t["weapon"]
                d.append(f"{wp.get('group')}, {wp.get('reach') or wp.get('range')}, Damage {wp.get('damage')} ({wp.get('damage_text')})"
                         + (", " + ", ".join(wp["qualities"]) if wp.get("qualities") else ""))
            if t.get("armour"): d.append(f"AP {t['armour']['ap']}: {', '.join(t['armour']['locations'])}")
            for k in ("worn", "stowed"):
                if t.get(k): d.append(k)
            if t.get("notes"): d.append(t["notes"])
            L.append(f"| {'– ' * t['depth']}{t['name']} | {t['qty']} | {t['enc']} | {t['counts']} | {'; '.join(d)} |")
    if m.get("money"):
        L.append("Money: " + ", ".join(f"{v} {k}" for k, v in m["money"].items()))
    for title, key in (("Ambitions", "ambitions"), ("Psychology", "psychology"), ("Mutations", "mutations")):
        v = m.get(key)
        if v:
            L += ["", f"## {title}"] + ([f"- {k}: {x}" for k, x in v.items() if x] if isinstance(v, dict) else [
                f"- {x}" if isinstance(x, str) else
                f"- {x['name']}" + (f" ({'; '.join(x['cells'])})" if x.get("cells") else "") +
                (f", from `{x['why']}`" if x.get("why") else "") + f" {x.get('cite', '')}".rstrip() for x in v])
    if m.get("effects"):
        L += ["", "## What rules add", "Already in the numbers above."]
        L += [f"- {CHAR_NAME.get(e['on'], e['on'].replace('_', ' ').capitalize())} " +
              (f"× {e['multiply']}" if "multiply" in e else f"{'+' if e['add'] >= 0 else ''}{e['add']}") + f": `{e['from']}`" for e in m["effects"]]
    more = [(t["name"], t["added_by"]) for t in m["talents"] if t.get("added_by")]
    if more:
        L += ["", "## Rules that add to these talents", "The build doesn't apply these: read them when checking the character."]
        L += [f"- {n}: " + ", ".join(f"`{r}`" for r in refs) for n, refs in more]
    if m["accepted"]:
        L += ["", "## Accepted differences"] + [f"- {d['text']} ({d['why']})" for d in m["accepted"]]
    if m["notes"]:
        L += ["", "## Not worked out"] + [f"- {n}" for n in m["notes"]]
    return "\n".join(L) + "\n"


def build(record, lib):
    return Builder(record, lib).build()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--md", action="store_true", help="the readable sheet instead of the JSON model")
    ap.add_argument("--shown", help="a hand-kept sheet's JSON (read_sheet_export.py) to compare the build with")
    ap.add_argument("--out")
    a = ap.parse_args()
    with open(a.record, encoding="utf-8") as f:
        rec = json.load(f)
    m = build(rec, Library(a.library, a.campaign))
    if a.shown:
        with open(a.shown, encoding="utf-8") as f:
            m["compared"] = compare(m, json.load(f))
    text = markdown(m) if a.md else json.dumps(m, indent=1, ensure_ascii=False) + "\n"
    if a.md and a.shown:
        text += "\n## The kept sheet shows something else\n" + ("".join(
            f"- {d['what']}: the sheet shows {d['shown']}, the build gives {d['built']}\n" for d in m["compared"]) or "- nothing\n")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f: f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    cli(main)
