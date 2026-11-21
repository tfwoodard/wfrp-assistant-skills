---
name: wfrp-rules-lookup
description: Answer Warhammer Fantasy Roleplay (4e) rules questions during play using the group's private library in Google Drive, with chapter, section and page citations. Use for questions like "how does Fear work", "what does the Ablaze condition do", "what's a Hard test", "what are the Rat Catcher's level 2 skills", "what's the CN of Aethyric Armour", or "look up the profile for a Giant Rat".
---

# Rules lookup

Read `references/library-layout.md` for where data lives and how to cite it.

## Approach

1. Resolve the library and the active campaign (layout §1, §8). Gather house
   rules from `library.json` and `campaign.json`; campaign rules win where they
   conflict.
2. Pick the likely categories (rules, talents, skills, spells, creatures,
   trappings, qualities, tables…) and find entries as layout §8 describes
   ("Finding entries for a campaign"): library, campaign, and, for the GM only,
   `gm/` library data, filtered by the sources in play. Match on `name` and
   `aliases`, case-insensitively, then open the best 1–5 entry files.
   Conditions and psychology are `rules` entries with `kind` `condition` or
   `psychology`. When the library is a folder the session can read (layout §1,
   or a copy holding at least the category `_index.json` files),
   `scripts/find_entry.py <name> [<name> …] --library <root> --campaign <slug>
   [--category rules,spells] [--gm]` does this search: for each name it gives
   the matching entries with their citation, their `.md` file, what their
   relations mean for the answer, the entries in play that add to it ("added
   to by": read those too, they change or extend it), and, apart, the entries
   the campaign doesn't use with the rule that removes each. `--gm` only when the user is the
   campaign's GM. Without a folder, read the indexes through the connector and
   apply the same rules.
3. If nothing matches, check the chapter lists (layout §3). If the relevant
   chapter of a source in play isn't imported yet, say so and suggest the
   Librarian import it (with `wfrp-import`). Don't read source PDFs yourself to
   fill the gap.
4. Answer for the table:
   - Lead with the ruling in one or two sentences a GM can read aloud.
   - Then the supporting rule, in your own words, with citations
     `(CRB, ch. 5 › Fear, p. 190)` (layout §5).
   - When the answer depends on exact wording (the user asks for it, or the
     ruling turns on a phrase), send the wording as a file, by default and
     without asking first, as layout §5 ("Exact wording") describes:
     `scripts/excerpt.py` with the refs `find_entry.py` gave. Don't quote the
     rule in the reply alongside the file.
   - If two sources in play have an entry of that name, follow the entries'
     relations (layout §8): use an entry with the one it adds to; of versions
     of one thing, the one from the source the campaign lists first (say the
     other exists); and say which you mean when they're distinct.
   - For tests, give the difficulty modifier and what SL means for this one.
   - Mention any house rule that changes the answer, and rules that interact
     with it (Ablaze + Prone, Fear + Broken).
   - If the rules are genuinely ambiguous, say so, give the most common
     reading, and note that the GM makes the call.
5. Keep it short. People are mid-session.

## Don'ts

- Don't answer from memory when the library is reachable. WFRP's editions
  differ in many small ways. If the library is unreachable and you answer from
  general knowledge, say so clearly.
- Don't reproduce book text in the chat, even briefly. Rule wording reaches
  the user as a file from `excerpt.py` (or the entry's own `.md` file); the
  reply paraphrases and cites.
- Never show GM-only entries (`audience: gm`, `gm/` data) to anyone but the
  campaign's GM.
