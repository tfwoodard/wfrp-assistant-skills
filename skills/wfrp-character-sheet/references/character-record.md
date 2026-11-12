# The character record (schema 1)

A character record is `characters/<slug>.json` in its campaign. It holds the
character's **choices and facts**, never what a rule decides: every rule it
names is a reference to a library entry, `"<category>/<slug>"`, and the sheet
reads that entry each time it is built.

```json
{
  "schema": 1,
  "slug": "greta-falkenhayn",
  "name": "Greta Falkenhayn",
  "player": "Sam",
  "species": { "ref": "species/human", "how": "rolled" },
  "careers": [
    { "ref": "careers/rat-catcher", "level": 2, "how": "rolled", "completed_levels": [1] }
  ],
  "characteristics": {
    "initial": { "WS": 31, "BS": 28, "S": 33, "T": 35, "I": 30, "Ag": 29, "Dex": 27, "Int": 26, "WP": 32, "Fel": 24 },
    "how": "rolled",
    "rolls": { "WS": [6, 5], "BS": [4, 4] }
  },
  "fate": 2, "resilience": 1, "extra_points": { "fate": 1, "resilience": 0 },
  "advances": [
    { "kind": "characteristic", "what": "WS", "count": 5, "xp": 125, "session": 3 },
    { "kind": "skill", "ref": "skills/melee", "specialisation": "Basic", "count": 5, "xp": 50, "session": 3 },
    { "kind": "talent", "ref": "talents/strike-mighty-blow", "times": 1, "xp": 100, "session": 4 },
    { "kind": "career-change", "ref": "careers/rat-catcher", "level": 2, "xp": 0, "session": 5 }
  ],
  "creation": {
    "skills": [ { "ref": "skills/animal-care", "count": 5, "from": "species/human" } ],
    "talents": [ { "ref": "talents/doomed", "from": "species/human" } ]
  },
  "xp": { "total": 520, "spent": 475, "bonus_at_creation": 70 },
  "spells": [],
  "trappings": [
    { "ref": "trappings/hand-weapon", "qty": 1, "carried": true },
    { "name": "Ratting terrier", "notes": "Small dog, follows Greta" }
  ],
  "money": { "gc": 0, "ss": 3, "bp": 14 },
  "state": {
    "wounds_taken": 0, "fortune_spent": 0, "resolve_spent": 0,
    "corruption": 1, "conditions": [], "critical_wounds": [], "insanities": []
  },
  "mutations": [],
  "psychology": [],
  "ambitions": { "short": "", "long": "" },
  "details": { "age": 24, "height": "", "eyes": "", "hair": "", "notes": "" },
  "incomplete": [],
  "notes": "",
  "changelog": [ { "date": "2026-11-14", "session": 7, "text": "Spent 100 XP on Strike Mighty Blow" } ]
}
```

| Field | Meaning |
|---|---|
| `species`, `careers[].ref` | References to the library entries. `how` is `rolled` or `chosen`, for the creation XP bonus. |
| `careers` | Every career the character has been in, oldest first; the last is current. `level` is the current level (1–4) in it; `completed_levels` the levels completed. |
| `characteristics.initial` | The starting values after species formulas, as rolled or allocated. Advances are in `advances`; the current value is worked out. |
| `advances` | Every XP purchase in order. `count` advances bought in one go; `xp` what they cost, worked out from the library's cost table when bought. A skill or talent with a specialisation names it. |
| `creation` | Advances and talents the character got free at creation, each with `from`: the entry that gave it. |
| `xp` | `total` earned (including creation bonus), `spent`. Current XP is `total − spent`. |
| `trappings` | Library trappings by `ref`, or anything else by `name`. |
| `state` | What changes in play. Wounds left, encumbrance and the rest are worked out. |
| `incomplete` | Things the player still has to settle; the sheet shows them at the top until they're fixed. |
| `changelog` | Every change, newest last. |

Characteristic codes are always `M WS BS S T I Ag Dex Int WP Fel W` as the
books print them. Keep the record's key order as above, so changes diff
cleanly.
