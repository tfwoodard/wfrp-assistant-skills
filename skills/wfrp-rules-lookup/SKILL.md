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
   trappings, qualities, tables…) and find entries as layout §8 describes:
   library, campaign, and, for the GM only, `gm/` library data, filtered by the
   sources in play. Match on `name` and `aliases`, case-insensitively, then open
   the best 1–5 entry files. Conditions and psychology are `rules` entries with
   `kind` `condition` or `psychology`.
3. If nothing matches, check the chapter lists (layout §3). If the relevant
   chapter of a source in play isn't imported yet, say so and suggest the
   Librarian import it (with `wfrp-import`). Don't read source PDFs yourself to
   fill the gap.
4. Answer for the table:
   - Lead with the ruling in one or two sentences a GM can read aloud.
   - Then the supporting rule text, quoted briefly, with citations
     `(CRB, ch. 5 › Fear, p. 190)` (layout §5).
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
- Don't paste long sections of book text into the chat; quote only what the
  ruling needs.
- Never show GM-only entries (`audience: gm`, `gm/` data) to anyone but the
  campaign's GM.
