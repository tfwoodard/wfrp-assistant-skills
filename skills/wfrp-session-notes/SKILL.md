---
name: wfrp-session-notes
description: Add, search, and recap Warhammer Fantasy Roleplay session notes for a campaign in the private Google Drive library. Use when the user pastes or points to their session notes or a recording transcript to save, asks what happened in a past session ("when did we meet the boatman?", "what did we find in Bögenhafen?"), wants a recap to read at the start of a session, wants XP or corruption totals from the sessions, or wants to list open threads and the party's ambitions.
---

# Session notes

Read `references/library-layout.md` first, especially §7 (access), §8
(campaigns), and §10 (sessions). Resolve the library and the active campaign
before anything else. If the campaign has no `sessions/` folder yet, create it
with `raw/` and an empty `_index.json`.

## Add a session

**Inputs**, in any combination:

- notes typed or pasted into the chat
- a transcript, pasted or as a Drive file (Google Doc, .txt, .vtt, .srt, .md).
  If the user attaches a file in the chat, save a copy to `sessions/raw/`.
- an audio or video file: say that you can't transcribe it here and ask for a
  transcript (most recording and meeting tools can export one)

**Steps:**

1. **Identify the session.** Default: next number after the highest in
   `_index.json`, and today's date. Ask only if the notes suggest otherwise. If
   that number already exists, ask whether to replace it or add to it.
2. **Save the source.** Save the original to
   `sessions/raw/<yyyy-mm-dd>-s<NN>-<notes|transcript>.<ext>`, exactly as given.
   Don't edit it. If there are several, add `-2`, `-3` and so on. If it's the
   GM's own prep or notes with secrets in them, save it in `gm/sessions/raw/`
   instead.
3. **For a transcript, map who's who.** Match speaker labels to players and
   characters using `campaign.json` → `party` (each party entry's `player` and
   its character record's `name`). Treat the speaker who narrates and voices
   NPCs as the GM. Show the mapping and ask the user to confirm or fix it once
   per transcript. Keep the mapping in the session file's front matter.
4. **Distill.** Write the session file (layout §10) from the source:
   - Focus on what happened in the game. Drop table talk unless it decided
     something, like a ruling the group agreed on (under **Rulings**).
   - Write in past tense, third person, using character names.
   - Record NPCs, locations, factions, items, and quests with the names used at
     the table. Reuse spellings from earlier sessions (check `_index.json`). If
     a name is new but probably the same as an existing one, ask.
   - Under **Advancement**, record XP awarded (and to whom, if it differs),
     and career changes. Under **Corruption and wounds**, record Corruption
     points gained, mutations, Critical Wounds and insanities that carry
     forward. Offer to apply them to the character records (via
     `wfrp-character-sheet`); don't change records yourself here.
   - Record the in-game date if the notes give it, and offer to update the
     campaign's `in_game_date`.
   - Don't make things up. If the source is unclear, say it's unclear and add
     it to **Open questions**.
   - Anything secret goes in the GM-only file instead, never in the shared file.
5. **Review.** Show the user the summary, the entity lists, XP and corruption,
   any open questions, and what's going to the GM-only file. Write after they
   confirm, or straight away if they said not to ask.
6. **Index.** Add or replace the session's record in `sessions/_index.json`
   (sorted by number) in the same pass, and in `gm/sessions/_index.json` if
   there's a GM-only file.
7. **Optional.** Offer to update `campaign.json` → `party` if a character
   joined, left or died, and `party_ambitions` if the party set new ones.
8. **The notebook.** Offer notes for what the party will need to remember next
   time (see "The notebook" below), and ask which current notes this session
   made no longer matter, to retire them.

## Scraps from sessions nobody wrote up

When the user has only fragments of earlier sessions ("we met a boatman called
Josef somewhere around the third session"), don't invent session files:

1. **Save the source** as for a session: `sessions/raw/history-<yyyy-mm-dd>.<ext>`
   (the date they were written down), exactly as given.
2. **Add each scrap** to `sessions/history.md` (layout §10, "History") under
   **Scraps**, in the order the sessions happened when that's known. Give a
   session only when the user remembers one ("around s3"); otherwise none. Keep
   their words' meaning; don't fill gaps. What's unclear goes under **Open
   questions**. Secrets go to `gm/sessions/history.md`.
3. **Names**: add each NPC, place, faction, item and quest to the history's
   front matter, with the spelling the group uses (check `_index.json` and the
   notebook first, and ask when a new name is probably an old one).
4. **Index**: the history's record in `sessions/_index.json` is session `0`,
   `"file": "history.md"`, with no date, its summary and name lists updated in
   the same pass.
5. **The notebook**: ask which of these still matter now, and add those as
   notes with `"from": "history"`.

Show the user the scraps, names and notes before writing, as for a session.

## The notebook

`notes.json` in the campaign folder (layout §10) holds what the group needs
to remember now. Each current note prints on the character sheets' play page:
the party's on every sheet, a character's own (`--for <slug>`) only on theirs.
Use `scripts/notebook.py` so the file keeps its shape:

```
python3 scripts/notebook.py <campaign folder> add --kind npc --name "Josef Quartjin" \
    --text "Captain of the Berebeli; gave us passage to Altdorf" --from 3
python3 scripts/notebook.py <campaign folder> add --kind item --name "Brass key" --text "..." --from history --for calfaric
python3 scripts/notebook.py <campaign folder> retire josef-quartjin --session 9 --why "left at Altdorf"
python3 scripts/notebook.py <campaign folder> list --current
```

- A note is one line: who or what, and why it matters, in the group's terms.
  Kinds: `npc`, `place`, `item`, `faction`, `thread`, `fact`.
- **Retire, don't delete.** When a note stops mattering, retire it with the
  session it stopped in (when known) and why. It stays in the notebook, in
  searches and in "who is X" answers; it leaves the sheets. `restore` brings
  it back if it matters again.
- Secrets go in the GM's notebook (`--gm`, `gm/notes.json`), which no sheet
  prints.
- After adding or retiring notes, rebuild the party's sheets
  (`wfrp-character-sheet`: `character_pdf.py --pdf`) so the play pages match,
  and upload the notebook, the history and the sheets.

The connector can't edit files in place. To change a file, write the new
version and move the old one to the trash; in the local folder, write over it.

## Search

1. Read `sessions/_index.json` (session 0 is the history of scraps) and the
   notebook, `notes.json`, retired notes included. Match the question against
   `title`, `summary`, `npcs`, `locations`, `factions`, `items`, `quests`, and
   `tags`, and the notes' names and text (case-insensitive; partial names are
   fine).
2. If the index doesn't settle it, search the text of the campaign's
   `sessions/` files (session files first, then `raw/` for exact wording).
   Search `gm/sessions/` too only when the user is the GM.
3. Open the matching session files and answer with session numbers and dates
   (and in-game dates when recorded). Quote a transcript only when the user
   wants the exact words.
4. If nothing matches, say so plainly. Don't guess from general Warhammer lore.

## Recaps and threads

- **"Previously on…"**: recap the last session (or the last N), short enough to
  read aloud in about a minute, ending on where the party is and what they were
  about to do. Use only the shared session files, never `gm/`.
- **Open threads**: collect `open_threads` from all sessions, drop any that a
  later session marked resolved, and group the rest by quest or NPC. Put the
  party's ambitions from `campaign.json` at the top.
- **XP so far**: total `xp_awarded` across sessions, and compare with each
  character record's XP total; report any difference rather than fixing it.
- **Who/what is X**: everything the notes say about an NPC, place, or item,
  in session order, with session numbers: the history's scraps first, then
  the sessions, and the notebook's note on it (saying if it's retired, and
  since when).

## GM-only content

If the user marks something as secret, or it's GM prep the players haven't
seen, write it to `gm/sessions/<same file name>.md`, never to the shared
session file. Only the campaign's GM can open `gm/`. If you can't write there,
stop and tell the user rather than putting it in the shared file. Use GM-only
notes in answers only when the user is the campaign's GM.
