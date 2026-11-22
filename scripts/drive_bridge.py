#!/usr/bin/env python3
"""Bookkeeping for writing library files to Drive through the claude.ai device bridge.

In a claude.ai session the library is changed in a local copy (/mnt/user-data/uploads/<folder>,
filled by device_stage_files) and written back with device_commit_files, which wants each file's
Drive modification time from its last download, so it never overwrites a change made since. This
script keeps those times and makes the batches; the bridge tools still do the transfers.

    drive_bridge.py record RESULT.json
        RESULT.json is a device_stage_files result ({"staged": [...]}) saved as it came: each file's
        Drive time, size and SHA-256 go in the ledger.
    drive_bridge.py push --batch NAME FILE... [--new]
        FILE is a file in the local copy of the library, or LOCAL=RELATIVE for a file elsewhere
        (RELATIVE is its path in the library, with / between folders). Each is copied to
        <outputs>/<NAME>/<RELATIVE>; the device_commit_files list (with expectedMtimeMs from the
        ledger) and the device_stage_files list to download them again are printed as JSON. A file
        the ledger has no time for is refused unless --new says it is new to Drive. Then it waits
        until the copies are WAIT seconds old: the bridge reads new output files a little late, and
        an earlier upload went up stale without the wait.
    drive_bridge.py verify --batch NAME RESULT.json
        RESULT.json is the device_stage_files result of downloading the batch again. Each download
        is compared with what the batch meant to upload; the ledger takes the new times. Exits 1 if
        any differs.

Where things are: --device-root (the library on the Librarian's computer; default
`drive_local_path` from wfrp-library.config.json), --mirror (the local copy; default
/mnt/user-data/uploads/<the device root's last folder>), --outputs (default /mnt/user-data/outputs),
--ledger (default drive-ledger.json beside this repo's wfrp-library.config.json; gitignored).
"""
import argparse, hashlib, json, os, shutil, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 25


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def device_path(root, rel):
    sep = "\\" if "\\" in root or (len(root) > 1 and root[1] == ":") else "/"
    return root.rstrip("\\/") + sep + rel.replace("/", sep)


def staged(result_path):
    data = load(result_path, None)
    if not isinstance(data, dict) or not isinstance(data.get("staged"), list):
        raise SystemExit(f"{result_path}: not a device_stage_files result ({{\"staged\": [...]}})")
    bad = [s.get("devicePath") for s in data["staged"] if not s.get("ok")]
    if bad:
        raise SystemExit(f"{result_path}: these didn't download: {', '.join(map(str, bad))}")
    return data["staged"]


def record(ledger, items):
    for s in items:
        entry = {"mtimeMs": s["mtimeMs"], "bytes": s.get("bytes")}
        if os.path.exists(s.get("stagedPath", "")):
            entry["sha256"] = sha(s["stagedPath"])
        ledger[s["devicePath"]] = entry
    return ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-root")
    ap.add_argument("--mirror")
    ap.add_argument("--outputs", default="/mnt/user-data/outputs")
    ap.add_argument("--ledger", default=os.path.join(ROOT, "drive-ledger.json"))
    ap.add_argument("--wait", type=int, default=WAIT, help="seconds a copy must be old before the upload (0 to skip)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("result")
    p = sub.add_parser("push"); p.add_argument("--batch", required=True); p.add_argument("files", nargs="+")
    p.add_argument("--new", action="store_true", help="files that aren't in Drive yet")
    v = sub.add_parser("verify"); v.add_argument("--batch", required=True); v.add_argument("result")
    a = ap.parse_args(argv)

    cfg = load(os.path.join(ROOT, "wfrp-library.config.json"), {})
    droot = a.device_root or cfg.get("drive_local_path")
    if not droot:
        raise SystemExit("give --device-root (or drive_local_path in wfrp-library.config.json)")
    mirror = a.mirror or os.path.join("/mnt/user-data/uploads", droot.rstrip("\\/").replace("\\", "/").split("/")[-1])
    ledger = load(a.ledger, {})

    if a.cmd == "record":
        items = staged(a.result)
        save(a.ledger, record(ledger, items))
        print(f"recorded {len(items)} Drive times in {a.ledger}")
        return 0

    bdir = os.path.join(a.outputs, a.batch)
    if a.cmd == "push":
        plan, commit, missing = [], [], []
        for spec in a.files:
            local, eq, rel = spec.partition("=")
            if not eq:
                full = os.path.abspath(local)
                if not full.startswith(os.path.abspath(mirror) + os.sep):
                    raise SystemExit(f"{local} isn't in the local copy of the library ({mirror}); write LOCAL=RELATIVE")
                rel = os.path.relpath(full, mirror).replace(os.sep, "/")
            if not os.path.isfile(local):
                raise SystemExit(f"{local} isn't a file")
            dev = device_path(droot, rel)
            known = ledger.get(dev)
            if not known and not a.new:
                missing.append(dev)
                continue
            out = os.path.join(bdir, *rel.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(local, out)
            item = {"stagedPath": out, "devicePath": dev}
            if known: item["expectedMtimeMs"] = known["mtimeMs"]
            commit.append(item)
            plan.append({"devicePath": dev, "batchPath": out, "sha256": sha(out)})
        if missing:
            raise SystemExit("no Drive time recorded for these, so they can't be uploaded safely: download them and "
                             "`record` the result first (or --new if they aren't in Drive yet):\n  " + "\n  ".join(missing))
        save(os.path.join(bdir, ".batch.json"), {"files": plan, "written": time.time()})
        print("device_commit_files files:")
        print(json.dumps(commit, ensure_ascii=False))
        print("device_stage_files paths, to download them again:")
        print(json.dumps([x["devicePath"] for x in plan], ensure_ascii=False))
        if a.wait > 0:
            time.sleep(a.wait)
        print(f"{len(plan)} files ready in {bdir}")
        return 0

    batch = load(os.path.join(bdir, ".batch.json"), None)
    if not batch:
        raise SystemExit(f"no batch '{a.batch}' in {a.outputs}")
    items = {s["devicePath"]: s for s in staged(a.result)}
    def check():
        good, bad = 0, []
        for f in batch["files"]:
            s = items.get(f["devicePath"])
            if not s:
                bad.append(f"{f['devicePath']}: not downloaded again")
            elif not os.path.exists(s["stagedPath"]) or sha(s["stagedPath"]) != f["sha256"]:
                bad.append(f"{f['devicePath']}: Drive has something else")
            else:
                good += 1
        return good, bad
    good, bad = check()
    if bad and a.wait > 0:                   # a download can land a moment after the result says so
        time.sleep(5)
        good, bad = check()
    save(a.ledger, record(ledger, list(items.values())))
    print(f"{good} of {len(batch['files'])} match")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
