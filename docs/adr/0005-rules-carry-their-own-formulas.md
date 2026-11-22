# Rules carry their own formulas; the builder only evaluates them

The character builder works out numbers from the library and reports where a
record and the rules disagree. Two kinds of rule it cannot see, because they
are only in an entry's prose:

- what a rule **does to a number** (a talent that adds to a starting
  characteristic or to Wounds). Today Claude reads each talent and writes the
  effect into every character's record by hand.
- what a rule **requires or limits** (a talent taken once per lore, an Elf
  allowed one lore per point of Willpower Bonus, so many advances before the
  next). Today Claude checks these by reading, every time a character is
  checked.

Writing those rules into the builder was rejected by the Librarian: every book
that changes a rule would mean rebuilding the tool, and five books in, three of
them already state one rule three ways. Reading stays the method. But the same
rule is read again for every character and every purchase, and each reading
can go wrong.

So a rule's formula is written **once, on the entry that states the rule**, and
the builder evaluates whatever formulas it finds on the entries a character
actually uses. A new book brings its own formulas; the builder does not change.

## Where a formula lives

In the entry's `fields`, beside the text it encodes, in two lists:

```json
"effects": [
  { "on": "WP", "add": 5, "at": 1 }
],
"checks": [
  { "id": "one-per-bonus",
    "applies": { "species": ["species/high-elves", "species/wood-elves"] },
    "test": { "count": { "talent": "talents/arcane-magic" }, "at_most": "WPB" },
    "at": 1 },
  { "id": "previous-lore-mastered",
    "read": "Each lore after the first has conditions on the one before it.",
    "at": 1 }
]
```

- `at` is the number of the entry's block that says so, so a reader goes
  straight to the sentence. The sentence itself is not copied.
- `effects` are what a character record's `effects` are now: a target, and a
  sum in the books' shorthand (`TB * times`).
- A check has a `test`, or a `read`, or both. `read` means "this part is not in
  the formula: read the entry". A rule that fits the vocabulary only in part is
  written in part, and says so.

The entry in the library is a formula's **only home**. `set_formulas.py`
writes it into the entry's `fields`; it is not copied into the index and no
part of it is kept in a chapter's plan (ADR 0006). A re-import writes the entry
afresh, so the converter copies the formulas over from the entry it replaces,
and lists any that no longer fit (the block gone, the row renamed) to be
written again. A formula that is lost is simply regenerated the next time the
rule is applied.

A **table's row** can carry formulas too, because some rules are rows: a
mutation, a result of a roll a talent sends you to. The row is named by the
text of one of its cells (the table entry's `fields.rows`: `{"<name>":
{"effects": [...]}}`), which must name exactly one row; the row is the place, so there is
no `at`. A character record names the row it has (`{"table": ..., "row": ...}`
under `psychology` or `mutations`), and that row's formulas are used.

## Which formulas are used

Only those on entries the character uses: the species and origin, careers,
talents, skills, spells and trappings the record names, and every entry in
play that **adds to** one of those (layout §4). Replacement follows the
relations as everywhere else: a replaced entry's formulas are not used.
Nothing is evaluated just because it exists in the library.

`applies` narrows a formula to the characters it is about (a species, a career,
a class, a level, or the specialisation the character took of the entry the
formula is on: a talent's chosen benefit). An effect on a price multiplies
rather than adds (`"on": "spell_cost", "multiply": 0.5`). A creation step's rule
gives XP with `"on": "xp"`, narrowed by `"applies": {"how": [...]}` to the way the
record says the step was settled (a roll kept, rolls rearranged). Two books may then state different numbers for different
characters without either replacing the other.

## What the builder does with them

- An effect is added to its number, with the entry as its source, exactly as a
  record's effect is. A record's own `effects` remain, for one-off cases.
- A failed test is a **difference**, `check:<entry>/<id>`, with the entry as
  its rule. Its text is the check's `says` (the requirement in Claude's own
  words) and what was found, in words ("Arcane Magic talents taken: 2, wanted
  at most 1"). Exceptions and house rules accept it like any other difference.
- A `read` is listed in the sheet's To do, with the entry, for Claude to read
  and apply, until an exception (or a house rule's `accepts`) names its id:
  then it is listed with the accepted differences and why. A check with both a
  test and a `read` is tested, and the `read` is listed too.
- Two formulas that both apply are both evaluated and both reported. The
  builder never chooses between books.
- A word the builder does not know is a note on the sheet, never skipped.

## The vocabulary is small and closed

Values: a characteristic or its bonus, or a sum of them as the species
formulas write it (`"WPB"`, `"WP + 10"`); `{"advances": skill, "specialisation"}`
(one specialisation or the highest); `{"times": talent, "specialisation"}` (one
specialisation or all); `{"count": {"talent"|"skill": ref or [refs]}}` (how many
of them are taken) or `{"count": {"spell": {"lore"|"kind"|"learned_under": name}}}`
(`lore` is the spell entry's own lore, which an Arcane spell hasn't; `learned_under`
is the lore the character learned it under, so it counts that Lore's spells and
the Arcane spells learned as part of it: the record's `lore` on the spell's line,
or the character's only lore); and
`{"species"|"career"|"class"|"level"|"status": true}`. A Wind and its Lore are
the same specialisation ("Hysh" is "Light"). Comparisons: `{"value": V,
"at_least"|"at_most"|"equals": W}`, where `equals` may list what it may be.
Combining: `all`, `any`, `not`.

Adding a word to it is a change to the builder and gets a decision of its own.
A rule that needs more than this is a `read`.

## Who writes them, and when

Claude proposes a formula when a rule is first applied to a character, shows
it beside the sentence, and the Librarian confirms it, as with a table's title
or a career's class. Not in one sweep of the library: most rules never touch a
character, and an unreviewed formula is worse than none. Effects first (they
are simple and the most repeated work), requirements after.

## Considered Options

- **Rule-specific checks in the builder.** Rejected: the tool would be rebuilt
  whenever a book changes a rule.
- **Reading only.** Kept as the fallback (`read`), rejected as the whole
  answer: the same reading is repeated for every character.
- **Formulas in each character's record** (as effects are now). Rejected: the
  rule is copied per character and goes stale when the entry is corrected.
- **A general expression language in entries.** Rejected: it could not be
  reviewed by reading it beside the sentence, and it would grow.

## Consequences

- The text remains the authority. A formula is an interpretation of it, and a
  wrong one is corrected on the entry.
- The record's `effects` shrink to exceptions; existing records keep working.
- The import report should list entries whose text names a number or a
  condition and that carry no formula, as candidates, without guessing them.
