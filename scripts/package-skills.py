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

    package-skills.py --compare players=<manifest.json from the library's skills/> \
                      [--compare gm=<manifest.json from a campaign's gm/skills/>] [--upload DIR]

--compare says which zips differ from the ones the given manifest describes (a path that doesn't
exist means nothing is there yet, so everything is new). --upload copies what has to be uploaded
(the changed zips, with that folder's README.md and manifest.json) into DIR/<folder>/, and leaves
DIR/<folder>/ empty when nothing changed.
"""
import argparse
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


def package(dist):
    """Build every folder's zips, README and manifest in `dist`; return {folder: manifest}."""
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
        version = json.load(f)["version"]
    shutil.rmtree(dist, ignore_errors=True)
    manifests = {}
    for who, folder, skills in (("players", "players", PLAYERS), ("GMs", "gm", GM)):
        if not skills:
            continue
        out = os.path.join(dist, folder)
        os.makedirs(out)
        manifest = {"version": version, "zips": {}}
        for s in skills:
            manifest["zips"][f"{s}.zip"] = build_zip(s, os.path.join(out, f"{s}.zip"))
        with open(os.path.join(out, "README.md"), "w") as f:
            f.write(readme(who, skills, version))
        with open(os.path.join(out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")
        manifests[folder] = manifest
    return manifests


def changed_zips(manifest, old_path):
    """The zips in `manifest` whose SHA-256 differs from the manifest at `old_path` (or all, if
    there is none), and the version that manifest names."""
    old = {}
    if os.path.exists(old_path):
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f)
    return [z for z, sha in manifest["zips"].items() if old.get("zips", {}).get(z) != sha], old.get("version")


def collect(dist, folder, zips, upload):
    """Copy a folder's changed zips, README and manifest into upload/<folder>/."""
    out = os.path.join(upload, folder)
    shutil.rmtree(out, ignore_errors=True)
    if not zips: return []
    os.makedirs(out)
    names = zips + ["README.md", "manifest.json"]
    for n in names:
        shutil.copyfile(os.path.join(dist, folder, n), os.path.join(out, n))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--compare", action="append", default=[], metavar="FOLDER=MANIFEST",
                    help="players=<path> or gm=<path>: the manifest.json now in Drive for that folder")
    ap.add_argument("--upload", metavar="DIR", help="with --compare: copy what needs uploading here")
    a = ap.parse_args()
    compare = dict(c.split("=", 1) for c in a.compare if "=" in c)
    bad = [c for c in a.compare if "=" not in c] + [k for k in compare if k not in ("players", "gm")]
    if bad: sys.exit(f"--compare takes players=<manifest> or gm=<manifest>, not {', '.join(bad)}")
    if a.upload and not compare: sys.exit("--upload needs --compare")
    subprocess.run([os.path.join(ROOT, "scripts", "sync-shared.sh")], check=True, stdout=subprocess.DEVNULL)
    unknown = set(os.listdir(os.path.join(ROOT, "skills"))) - set(PLAYERS + GM + LIBRARIAN)
    if unknown:
        sys.exit(f"skills not assigned to players, GMs or the Librarian: {', '.join(sorted(unknown))}")
    dist = os.path.join(ROOT, "dist")
    manifests = package(dist)
    for folder, manifest in manifests.items():
        for k, v in manifest["zips"].items():
            print(f"dist/{folder}/{k}  {v[:12]}")
    for folder, path in compare.items():
        if folder not in manifests:
            print(f"{folder}: no skills are packaged for it")
            continue
        zips, was = changed_zips(manifests[folder], path)
        now = manifests[folder]["version"]
        if not zips:
            print(f"{folder}: nothing to upload (Drive has {was}; every zip is the same in {now})")
            if a.upload: collect(dist, folder, [], a.upload)
            continue
        print(f"{folder}: {len(zips)} changed since {was or 'nothing in Drive'} -> {now}: {', '.join(zips)}")
        if a.upload:
            names = collect(dist, folder, zips, a.upload)
            print(f"  to upload, in {os.path.join(a.upload, folder)}: {', '.join(names)}")


if __name__ == "__main__":
    main()
