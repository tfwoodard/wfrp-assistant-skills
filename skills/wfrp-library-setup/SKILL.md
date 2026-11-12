---
name: wfrp-library-setup
description: Set up, connect, upgrade, or check the private Warhammer Fantasy Roleplay library in Google Drive, and create or configure campaigns in it. Use when the user wants to start a new WFRP library, point Claude at an existing library folder, create a campaign or change its sources in play, house rules, character creation options, bans, party ambitions or GM, set up sharing for the group, find out why the other WFRP skills can't find their data, or see the library's health.
---

# WFRP library setup

Read `references/library-layout.md` first. It defines the folder structure,
`library.json`, `campaign.json`, access rules, and how the library is located.
Adding sources and importing chapters belong to `wfrp-import`.

## Connect to an existing library

1. Resolve the library root as described in layout §1.
2. Read `library.json`. Report the name, edition, layout version, and sources.
   If `layout_version` is below the layout's, offer **Upgrade** first.
3. Run the **health check** below.
4. If the user is in Claude Code and no `wfrp-library.config.json` exists,
   offer to write one from `wfrp-library.config.example.json` with the
   resolved folder ID and `drive_local_path` (needed for importing PDFs).
   Confirm it is not tracked (`git check-ignore wfrp-library.config.json`).
5. On claude.ai, suggest these lines for the Project's instructions, so every
   chat in the Project finds the library:
   "WFRP library: <folder URL>" and "WFRP library folder: <local path>".

## Create a new library

The person creating it becomes the Librarian.

1. Ask for the folder (an empty folder they made, or a parent and a name;
   default `WFRP Assistant`). If the folder already has files, list them and
   ask before adding anything.
2. Create `sources/`, `skills/`, `library-data/` with every category subfolder
   (layout §2), and `campaigns/`.
3. Write `library.json` (layout §3) with an empty `sources` list and `edition`
   `4e`. Write an empty `library-data/_import-log.json` (`[]`) and an empty
   `_index.json` (`[]`) in each category folder.
4. Connect it as above. Then suggest adding the Rulebook with `wfrp-import`,
   and creating the first campaign (below).

In the local folder, create folders and files directly; through the connector,
create each folder and file with Drive tools.

## Create or edit a campaign

1. Ask for the campaign name (make the slug: lowercase, hyphenated) and who
   the GM is.
2. Ask which library sources are in play [all of them], how characters are
   created (layout §8 `creation`) [the Rulebook's rules], and any campaign
   house rules or bans. Adventures and homebrew are added later through
   `wfrp-import` as campaign sources; they go first in `sources`. Leave
   `party` empty unless characters already exist.
3. Create `campaigns/<slug>/` with `campaign.json` (layout §8), `characters/`,
   `sessions/` (with `raw/` and an empty `_index.json`), `sources/`, and
   `library-data/` (with an empty `_import-log.json`; category folders and
   their indexes are created as entries arrive).
4. Create `gm/` with `skills/`, `sources/`, `library-data/` (same contents),
   `npcs/`, and `sessions/` (with `raw/` and an empty `_index.json`). Turn off
   inherited access on `gm/` (`inheritedPermissionsDisabled: true`) and share
   it with the GM only. Confirm afterwards that its permissions list only the
   GM (and the owner, if Drive requires it), and say so. If the folder was made
   in the local folder, do the access step through the connector.
5. To edit a campaign, read `campaign.json`, show the change as a short diff,
   and write it back. Check that every code in `sources` exists in
   `library.json` or `campaign_sources`, and that every `include`/`exclude`
   slug exists in that category's indexes. Warn about slugs not imported yet,
   but don't block on them.
6. In Claude Code, offer to set `default_campaign` in `wfrp-library.config.json`.

## Sharing

Set up access as layout §7 describes, when the user gives the group's email
addresses:

- library root: Librarian as owner or editor, everyone else as viewer
- each `campaigns/<slug>/`: its GM and players as editors
- each `gm/`: its GM only, with inherited access off

Show the planned changes and get confirmation before sharing anything.

The Drive connector can only add someone or raise their role; it can't lower or
remove access, and it can be refused by Drive's sharing quota ("Resource has
been exhausted"). So:

- **Tightening access is the user's step.** When someone has more access than
  this list allows, ask the user to change it in Drive's Share dialog, naming
  the folder, the person and the role.
- **Order matters.** Lower the parent first, then add the higher role on the
  child (players as editors of their campaign folder), or Drive treats the add
  as no change.
- **When the connector is refused**, give the user the same exact steps.
- **Check afterwards, every time.** List the permissions on the library root,
  `campaigns/`, each campaign folder and its `gm/`, and show them against this
  list.

## Upgrade

Show the plan before starting. Each layout version's upgrade steps go here as
the layout changes. (Layout 1 is the first.)

## Health check

Report a short table with:

- whether `library.json` exists and parses, and its `layout_version`
- how the library is reached: the local folder (layout §1), or the connector
- each source: kind, whether its file exists, `page_offset`, and its chapters
  by status (imported / problems / not imported)
- each `library-data/` category: entry count from `_index.json`, and any index
  slugs whose `.json` or `.md` file is missing (spot-check up to 10)
- the last 5 records of `_import-log.json`
- each campaign: its GM, sources in play (flag unknown codes), campaign
  sources and their chapter statuses, house rule count, party size (flag
  missing records), session count and latest date, whether `gm/` exists and
  is restricted to the GM

End with the single most useful next step, usually "import <source> <chapter>"
with `wfrp-import`.
