# The character record (schema 2)

A character record is `characters/<slug>.json` in its campaign. It holds the
character's **choices and facts**, never what a rule decides: every rule it
names is a reference to a library entry, `"<category>/<slug>"` (with
`#Heading` for a part of one), and `scripts/build_character.py` reads that
entry each time it builds the sheet. So a corrected or newly imported source
shows up on the next build, and nothing in the record goes stale.

```json
{
  "schema": 2,
  "slug": "greta-falkenhayn",
  "name": "Greta Falkenhayn",
  "player": "Sam",
  "species": { "ref": "species/humans", "origin": null, "how": "rolled" },
  "careers": [
    { "ref": "careers/rat-catcher", "level": 2, "how": "rolled", "left_incomplete": [] }
  ],
  "characteristics": {
    "initial": { "WS": 31, "BS": 28, "S": 33, "T": 35, "I": 30, "Ag": 29, "Dex": 27, "Int": 26, "WP": 32, "Fel": 24 },
    "how": "rolled",
    "rolls": { "WS": [6, 5], "BS": [4, 4] }
  },
  "extra_points": { "fate": 2, "resilience": 1 },
  "motivation": "Coin",
  "effects": [
    { "on": "wounds", "add": "TB * times", "from": "talents/hardy" }
  ],
  "advances": [
    { "skill": "skills/animal-care", "count": 5, "how": "species" },
    { "talent": "talents/doomed", "how": "species" },
    { "skill": "skills/melee", "specialisation": "Basic", "count": 10, "how": "career" },
    { "characteristic": "WS", "count": 5, "how": "xp", "session": 3 },
    { "talent": "talents/hardy", "how": "xp", "session": 4 },
    { "career": "careers/rat-catcher", "level": 2, "how": "xp", "xp": 100, "session": 5 },
    { "skill": "skills/lore", "specialisation": "Reikland", "count": 1, "how": "free", "notes": "The GM's award" }
  ],
  "spells": [ { "ref": "spells/dart", "how": "xp" } ],
  "xp": { "total": 520, "spent": 475, "bonus_at_creation": 70 },
  "trappings": [
    { "ref": "trappings/hand-weapon" },
    { "id": "pack", "ref": "trappings/backpack", "worn": true },
    { "ref": "trappings/rations-1-day", "qty": 3, "in": "pack" },
    { "name": "Ratting terrier's collar", "enc": 0, "in": "pack", "notes": "Brass, engraved" },
    { "ref": "trappings/tent", "stowed": true }
  ],
  "money": { "gc": 0, "ss": 3, "d": 14 },
  "state": {
    "wounds_taken": 0, "fortune_spent": 0, "resolve_spent": 0,
    "corruption": 1, "conditions": [], "critical_wounds": [], "insanities": []
  },
  "mutations": [],
  "psychology": [],
  "ambitions": { "short": "", "long": "" },
  "details": { "age": 24, "height": "", "eyes": "", "hair": "" },
  "exceptions": [
    { "id": "talent-max:hardy", "why": "The GM allowed a second Hardy after the fever", "house_rule": null }
  ],
  "incomplete": [],
  "notes": "",
  "changelog": [ { "date": "2026-11-14", "session": 7, "text": "Spent 100 XP on Hardy" } ]
}
```

| Field | Meaning |
|---|---|
| `species.ref`, `careers[].ref` | The library entries. `how` is `rolled`, `chosen` or `imported`, for the creation XP bonus. |
| `species.origin` | A homeland or kindred with its own skills and talents, as a ref to its heading (`rules/<entry>#<Heading>`). Its lists stand in for the species' own. Left out or null when the species entry's lists apply. |
| `careers` | Every career the character has been in, oldest first; the last is current. `level` is the level reached in it. `left_incomplete` lists the levels left before completing them (200 XP instead of 100), so the build doesn't report them. |
| `characteristics.initial` | The starting values as rolled or allocated, before anything a talent adds (those are `effects`). The build reports a value the species' roll can't give. |
| `extra_points` | How the species' extra points were shared between Fate and Resilience. |
| `effects` | What a rule does to a number, written when the talent or other rule is taken: `on` is a characteristic code, `wounds`, `movement`, `fate`, `resilience`, `encumbrance` or `corruption`; `add` a number or a sum in the books' shorthand (`SB`, `TB`, `WPB` and the other bonuses, the characteristic codes, and `times` for how often the `from` talent has been taken); `from` the entry that says so. The build can't read a talent's text, so an effect left out is a number left wrong: read each talent taken and write its effect. |
| `advances` | Everything gained, in the order it was gained: one line per gain, naming a `characteristic` (code), a `skill`, a `talent` or a `career` (a change of level or career). `count` advances for characteristics and skills, `times` for talents (1 when left out); `specialisation` for a grouped skill or talent. `how` says where it came from: `species` or `career` (free, at creation), `xp`, `free` (given in play), or `imported` (from a sheet kept elsewhere, history unknown). |
| `advances[].xp` | Leave out: the build works out the price from the library's cost tables, the number already taken, and whether the career lists it. Write it only for a career change (which the build can't price) or when something else was actually paid; the build then reports the difference. |
| `spells` | Spells memorised, by ref. |
| `xp` | `total` earned (including the creation bonus). `spent` only when it can't be worked out from `advances` (an imported character); otherwise leave it out. |
| `trappings` | Library trappings by `ref`, or anything else by `name` with its `enc`. `id` names a container so other lines can be `in` it (only the container's own Encumbrance counts); `worn` takes 1 off; `stowed` is owned but not carried. Armour counts on the sheet's locations only when `worn`. |
| `state` | What changes in play. Wounds left, Fortune and Resolve left are worked out. |
| `exceptions` | Differences from the rules the group has settled for this character, by the difference's `id`, with `why`, and `house_rule` when a campaign house rule is the reason. See below. |
| `incomplete` | Things the player still has to settle; the sheet shows them at the top until they're fixed. |
| `changelog` | Every change, newest last. |

Characteristic codes are always `WS BS S T I Ag Dex Int WP Fel` as the books
print them. Keep the record's key order as above, so changes diff cleanly.

## What the build gives back

`build_character.py RECORD --library ROOT --campaign SLUG` prints the model
(`--md` the readable sheet): characteristics with bonuses, movement with Walk
and Run, Wounds, Fate and Fortune, Resilience and Resolve, the Corruption
threshold, Encumbrance carried and the limit, every basic skill and each
advanced skill taken (with whether the career lists it), talents with how often
taken and their Max as a number, spells with ranges and durations in this
character's numbers, trappings with weapon damage worked out, armour by
location, XP, and three lists:

- **`differences`**: where the record and the rules disagree, each with an `id`
  (`initial:WP`, `talent-max:hardy`, `level-complete:rat-catcher/1`,
  `xp-overspent` …), a sentence, and the `rule` it comes from. The build never
  changes a number to fit a rule: the sheet shows what the record says.
- **`accepted`**: differences matched by one of the record's `exceptions` or by
  a campaign house rule's `accepts` (layout §8). They stay visible, with why.
- **`notes`**: what the build could not work out, and why. Nothing is left out
  without a note.

A difference is settled in one of three ways, and it is the player's and the
GM's choice which: fix the record (it was a mistake), write an exception (this
character, this once), or write a house rule in `campaign.json` (the group plays
it that way). Never write an exception to quieten a difference nobody has
looked at.

## A character kept on a sheet

`scripts/read_sheet_export.py EXPORT > shown.json` reads the group's
hand-kept spreadsheet (as the Drive connector reads it) into JSON: what the
sheet says, not a record. Write the record from it, resolving each name to its
entry (`find_entry.py`), with `how: "imported"` on every advance whose history
the sheet doesn't give, `xp.spent` as the sheet has it, and anything unclear in
`incomplete`. Then `build_character.py ... --shown shown.json` adds
`compared`: each number the sheet shows and the build works out differently.
Go through those and the differences with the player before changing anything.

`scripts/needs.py RECORD --library ROOT --campaign SLUG` lists the library
files a build reads and which aren't in this copy of the library, when it is
reached through the Drive connector rather than a folder.
