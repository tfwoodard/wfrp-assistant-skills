# Creation rules grant what a character starts with

A new character gets advances and talents free from its species and its first
career level: so many skills at so many advances, so many advances to share
out with at most so many in one, one talent. A record marks those lines `how:
species` or `how: career`. Until now nothing checked them, so a record could
claim any number of free advances.

The numbers are in the creation rules' prose, and ADR 0005 keeps rule numbers
out of the builder. Its checks vocabulary can count things, but not "three
skills at 5 and three at 3" in one formula, and a creation rule is not an entry
the character *uses* (a species or a talent), so its formulas would never be
read.

So a creation rule carries **grants**, a third kind of formula beside effects
and checks, set with `set_formulas.py --grants` and confirmed by the Librarian
like any other:

```json
"grants": [
  { "id": "skills", "how": "species", "kind": "skill", "from": "species",
    "picks": [{ "count": 3, "advances": 5 }, { "count": 3, "advances": 3 }], "at": 0 },
  { "id": "skills", "how": "career", "kind": "skill", "from": "first-career-level",
    "total": 40, "most": 10, "at": 0 },
  { "id": "talent", "how": "career", "kind": "talent", "from": "first-career-level",
    "count": 1, "at": 0 }
]
```

- `how` is the record's word for where the lines came from; `kind` is skill,
  talent or characteristic; `from` is the list they must be on: the species'
  (its origin's, when one is chosen) or the first career level's.
- What is given: `picks` (exactly so many at so many advances, each skill's
  lines of that `how` added up), `total` with `most`, or `count`. With none of
  them, only where the lines come from is checked.

## Which rules are read

The builder names the creation rules (species skills and talents, career skills
and talents, characteristic advances), as it names the cost table and the
level advances table; the numbers come from the entries. The version in play is
used, and every entry in play that adds to one of them adds its grants: a book
that gives Elder characters extra advances does so with its own grants, and
the builder does not change.

## What the builder does with them

- More than a grant gives, or a line from a list the grant doesn't name, is a
  difference, `creation:<rule>/<id>`. A `species` or `career` line of a kind no
  grant covers is `creation:<how>-<kind>`.
- What is left to share out is reported (`creation` in the build), for
  creating a character; a finished character may leave some unspent.
- With no grants on the creation rules, nothing is checked and the sheet says so.

## Considered Options

- **Numbers in the builder.** Rejected, as in ADR 0005.
- **Checks with a counting test.** Rejected: one creation step would need a
  cluster of tests, unreadable beside its sentence, and the rule entries would
  still not be read.
- **Grants on the species and career entries.** Rejected: the allowance is the
  same for every species and career, stated once in the creation rules.

## Consequences

- Random species talents ("3 Random Talents") are not yet a grant: such a
  talent fails the species list and is a difference to read and accept.
- `from` and the three ways of giving are a closed vocabulary; a new one is a
  decision of its own.
