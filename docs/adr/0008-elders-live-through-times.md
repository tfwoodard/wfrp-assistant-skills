# Elders live through Times, each with a career and a burden

Some books let a character start older than its species' usual age: an
*Elder*. The Elder picks the Time they were born in from a table, and has lived
through that Time and every later one. Each Time gives an earlier career, with
advances to spend on its first level's skills (more for a career rolled than
for one chosen, at most so many in one skill each Time), and a burden: a
number changed at creation (one Extra Point fewer, Fate set to 0), a trait the
character takes, or something to do in play. Some burdens don't add up: only
the earliest Time's applies.

ADR 0005 keeps rule numbers out of the builder and ADR 0007 gives creation
rules their grants. Neither could say "once per Time, from the career of that
Time", nor which Times a character lived through.

## Decision

The **record** says who is an Elder: `species.elder` is `{"born": <Time>,
"careers": [{"time", "ref", "how": "rolled"|"chosen"}]}`, and the advances
spent on those careers are lines with `how: "elder"` and the `time` they came
from.

The **rule entry** carries everything else, written with `set_formulas.py` and
confirmed by the Librarian like any formula:

- `lived_through`: `{"table": <title>, "column": <the column naming each
  Time>}`. The Times are that column's cells, in the table's order, newest
  first: an Elder born in a row has lived through that row and every row
  before it. The table may sit inside a sidebar.
- a **grant** with `"from": "elder-career"` and `"how": "elder"`: `total` (a
  number, or by `how`: `{"rolled": 15, "chosen": 10}`) and `most`, applied once
  per Time to that Time's career: only skills of its first level, at most
  `most` in one, at most `total` in all. The entry `adds-to` a creation rule so
  the builder reads it.
- **row formulas** for each Time, beside `effects` and `checks`: `careers` (how
  many earlier careers the Time gives; 0 for the usual age), `psychology` (the
  traits it gives, which the record must list, as it lists any other), and
  `burdens` (`[{"text", "only_earliest"}]`: lines in our own words for the
  sheet; an `only_earliest` line counts only from the Time of birth).

Two words join the **effects**: the target `extra_points` (what the species
gives to share between Fate and Resilience), and `set`, which replaces the
number after every `add` (the last one read wins).

The builder reads the Times, checks the careers and their advances
(`creation:<rule>/<id>:...`, `elder:...` differences), applies the burdens'
effects, and prints an Elder section: the Time of birth, each earlier career
with the advances given and left, and the burdens.

## Considered Options

- **The Times written in the builder.** Rejected, as in ADR 0005: another book
  could give Dwarfs or Wood Elves their own Times.
- **The Times listed on the entry.** Rejected: the table already prints them in
  order; `lived_through` only says which table and column.
- **The Elder's careers in the record's `careers`.** Rejected: those are the
  careers the character is in, with levels, completion and XP. An earlier
  career is none of that.
- **Burdens added to the record's psychology by the build.** Rejected: the
  record lists every trait the character has, as with Hollow Heart; the build
  says when one is missing.

## Consequences

- `elder-career` joins the closed vocabulary of where a grant's lines come
  from, and `careers`, `psychology` and `burdens` that of a row's formulas.
- The species and career grants are checked as before; an Elder's grant is
  checked on its own.
- A burden the vocabulary can't apply (an Endeavour limit, a weekly Test) is a
  line on the sheet, never a guess.
