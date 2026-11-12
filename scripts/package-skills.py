#!/usr/bin/env python3
"""Package the skills for the group to upload to claude.ai (Settings > Capabilities > Skills).

    dist/players/<skill>.zip   player skills: uploaded to the library's skills/ folder
    dist/gm/<skill>.zip        GM-only skills: uploaded to each campaign's gm/skills/ folder
    dist/<folder>/README.md      what's there, the version, how to install
    dist/<folder>/manifest.json  the version and each zip's SHA-256, uploaded with the zips, so the
                                 next packaging can tell which zips changed

The Librarian's skills (library setup and import) are never packaged: they're used from the repo.
Zips are reproducible (fixed timestamps and order), so an unchanged skill gives identical bytes and
only changed zips need uploading.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYERS = ["wfrp-rules-lookup", "wfrp-character-sheet", "wfrp-session-notes"]
GM = []                                          # GMs also get the player skills from the library root
LIBRARIAN = ["wfrp-library-setup", "wfrp-import"]  # repo only
SKIP = ("__pycache__", ".DS_Store")
STAMP = (2020, 1, 1, 0, 0, 0)


def build_zip(skill, out):
    base = os.path.join(ROOT, "skills")
    files = []
    for d, dirs, names in os.walk(os.path.join(base, skill)):
        dirs[:] = sorted(x for x in dirs if x not in SKIP)
        files += [os.path.join(d, n) for n in names if n not in SKIP and not n.endswith(".pyc")]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):
            info = zipfile.ZipInfo(os.path.relpath(f, base), STAMP)
            info.external_attr = (0o755 if os.access(f, os.X_OK) else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(f, "rb") as fh:
                z.writestr(info, fh.read())
    with open(out, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def readme(who, skills, version):
    lines = [f"# WFRP Assistant skills for {who} (version {version})", "",
             "Upload each zip in claude.ai under **Settings → Capabilities → Skills → Upload skill**,",
             "replacing an older copy of the same skill. You also need the **Google Drive** connector",
             "(Settings → Connectors), since the skills read the group's library from Drive.", ""]
    lines += [f"- `{s}.zip`" for s in skills]
    if who == "GMs":
        lines += ["", "GMs also use the player skills in the library's `skills/` folder."]
    return "\n".join(lines) + "\n"


def main():
    subprocess.run([os.path.join(ROOT, "scripts", "sync-shared.sh")], check=True, stdout=subprocess.DEVNULL)
    unknown = set(os.listdir(os.path.join(ROOT, "skills"))) - set(PLAYERS + GM + LIBRARIAN)
    if unknown:
        sys.exit(f"skills not assigned to players, GMs or the Librarian: {', '.join(sorted(unknown))}")
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
        version = json.load(f)["version"]
    shutil.rmtree(os.path.join(ROOT, "dist"), ignore_errors=True)
    for who, folder, skills in (("players", "players", PLAYERS), ("GMs", "gm", GM)):
        if not skills:
            continue
        out = os.path.join(ROOT, "dist", folder)
        os.makedirs(out)
        manifest = {"version": version, "zips": {}}
        for s in skills:
            manifest["zips"][f"{s}.zip"] = build_zip(s, os.path.join(out, f"{s}.zip"))
        with open(os.path.join(out, "README.md"), "w") as f:
            f.write(readme(who, skills, version))
        with open(os.path.join(out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")
        for k, v in manifest["zips"].items():
            print(f"dist/{folder}/{k}  {v[:12]}")


if __name__ == "__main__":
    main()
