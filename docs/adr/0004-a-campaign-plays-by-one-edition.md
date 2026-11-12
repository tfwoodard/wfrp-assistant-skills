# A campaign plays by one edition; older books add only what wasn't updated

Carried over from the DnD Assistant (its ADR 0005). Groups mine older WFRP
material (2nd edition's *Tome of Salvation*, 1st edition's *Enemy Within*
supplements) for lore and adventures while playing 4th edition rules. A
campaign must not mix editions' rules: a 2e career or spell that 4e updated is
never offered beside the 4e one, but the older book's places, history,
organisations and adventure material are still wanted.

So every source and index record carries its `edition`, a campaign plays by
one edition (by default the library's, `4e`), and an older entry that a newer
one updated gets an `updated-by` relation to it, under the same name or
another. In a campaign of the newer edition, that entry doesn't exist.
Everything else from the older source appears, read through the campaign's
edition's rules. Which entries were updated is a judgment call: each chapter's
plan proposes them and the Librarian confirms.

## Considered Options

- **Match by name only.** Rejected: careers and spells were renamed between
  editions.
- **Hide everything from older editions.** Rejected: the lore and adventures
  are why the books are in the library.
