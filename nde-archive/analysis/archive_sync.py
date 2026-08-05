#!/usr/bin/env python3
"""Mirror the extracted corpus into a private archive repository.

Why this exists: the corpus is ~630 MB of first-person accounts that are jointly
copyrighted by their authors and the foundations that host them. It is not ours
to publish, so it is kept out of the public repository entirely. But it should
not exist only on one laptop either — a disk failure would mean re-scraping
every account, and any future re-run would produce a slightly different corpus
because the archives keep growing.

So this writes a compressed mirror into a SEPARATE, PRIVATE repository:
private storage of material lawfully accessed for research, not publication.

    output/*.md         ->  corpus/*.md.gz          (62 MB -> 15 MB)
    analysis/data/*.jsonl -> corpus/*.jsonl.gz      (101 MB -> 19 MB)
    analysis/extraction/labels.json  ->  derived/   (annotations, not text)
    analysis/tier3/records_all.json  ->  derived/

Compression is not cosmetic: GitHub refuses any file over 100 MB, and
nderf.jsonl alone is 101 MB uncompressed.

The scrape cache (374 MB of raw HTML) is deliberately excluded — it is
regenerable and would triple the repository for no benefit.

Usage:
    python3 analysis/archive_sync.py --dest ../nde-corpus-private
    python3 analysis/archive_sync.py --dest ../nde-corpus-private --push
"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CORPUS = [
    (os.path.join(ROOT, "output", "%s.md"), "corpus"),
    (os.path.join(HERE, "data", "%s.jsonl"), "corpus"),
]
SITES = ("nderf", "adcrf", "oberf")
DERIVED = [
    (os.path.join(HERE, "extraction", "labels.json"), "derived/element_labels.json"),
    (os.path.join(HERE, "tier3", "records_all.json"), "derived/deep_coded_records.json"),
    (os.path.join(HERE, "manifest.json"), "derived/url_manifest.json"),
]

README = """# NDE corpus — private mirror

Compressed mirror of the extracted archives of nderf.org, adcrf.org and
oberf.org, plus the derived annotations used by the public analysis.

**This repository is private and must stay private.** Every account here is
jointly copyrighted by the person who wrote it and the foundation that hosts it,
and many contributors did not grant permission to publish their words anywhere
other than the original site. This mirror exists so the research corpus survives
a disk failure and so a given analysis can be reproduced against the exact
snapshot it was run on — not for redistribution.

To read any account as its author published it, use the source archives:
nderf.org, adcrf.org, oberf.org.

## Layout

    corpus/*.md.gz        one file per archive, the extracted accounts
    corpus/*.jsonl.gz     the same accounts parsed into records
    derived/              element labels and deep-coded annotations (no account text)
    SNAPSHOT.json         counts, byte sizes and checksums for this snapshot

## Restoring

    gunzip -c corpus/nderf.md.gz > nderf.md

Public methodology and findings:
https://souls.earth
"""


def gz(src, dest, log):
    """Compress, but only rewrite when the content actually differs.

    gzip embeds a timestamp, so a naive re-compress produces a different file
    every run and the repository would gain a fresh 50 MB commit daily even when
    nothing changed.
    """
    with open(src, "rb") as handle:
        raw = handle.read()
    digest = hashlib.sha256(raw).hexdigest()

    marker = dest + ".sha256"
    if os.path.exists(dest) and os.path.exists(marker):
        with open(marker, encoding="utf-8") as handle:
            if handle.read().strip() == digest:
                log("    unchanged  %s" % os.path.basename(dest))
                return digest, len(raw), os.path.getsize(dest)

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # mtime=0 keeps the output byte-identical for identical input
    with gzip.GzipFile(dest, "wb", compresslevel=9, mtime=0) as out:
        out.write(raw)
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write(digest + "\n")
    log("    wrote      %-22s %6.1f MB -> %5.1f MB"
        % (os.path.basename(dest), len(raw) / 1048576, os.path.getsize(dest) / 1048576))
    return digest, len(raw), os.path.getsize(dest)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", required=True, help="path to the private archive repo")
    parser.add_argument("--push", action="store_true", help="commit and push when done")
    args = parser.parse_args(argv)
    log = lambda m: print(m, flush=True)

    dest = os.path.abspath(args.dest)
    os.makedirs(dest, exist_ok=True)
    log("[archive] mirroring into %s" % dest)

    snapshot = {"date": date.today().isoformat(), "files": {}}

    log("  corpus")
    for template, folder in CORPUS:
        for site in SITES:
            src = template % site
            if not os.path.exists(src):
                continue
            name = os.path.basename(src) + ".gz"
            digest, raw_size, gz_size = gz(src, os.path.join(dest, folder, name), log)
            snapshot["files"][folder + "/" + name] = {
                "sha256_uncompressed": digest, "bytes_raw": raw_size, "bytes_gz": gz_size}

    log("  derived")
    for src, rel in DERIVED:
        if not os.path.exists(src):
            log("    missing    %s" % os.path.basename(src))
            continue
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        with open(src, "rb") as handle:
            snapshot["files"][rel] = {
                "sha256": hashlib.sha256(handle.read()).hexdigest(),
                "bytes": os.path.getsize(src)}
        log("    copied     %s" % rel)

    for site in SITES:
        path = os.path.join(HERE, "data", "%s.jsonl" % site)
        if os.path.exists(path):
            snapshot.setdefault("accounts", {})[site] = sum(1 for _ in open(path, encoding="utf-8"))
    snapshot["accounts_total"] = sum(snapshot.get("accounts", {}).values())

    with open(os.path.join(dest, "SNAPSHOT.json"), "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=1)
    with open(os.path.join(dest, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(README)
    with open(os.path.join(dest, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("*.sha256\n.DS_Store\n")

    total = sum(f.get("bytes_gz", f.get("bytes", 0)) for f in snapshot["files"].values())
    log("[archive] %d accounts, %.1f MB stored" % (snapshot["accounts_total"], total / 1048576))

    if args.push:
        run = lambda *a: subprocess.run(a, cwd=dest, check=False, capture_output=True, text=True)
        if not os.path.isdir(os.path.join(dest, ".git")):
            run("git", "init", "-q")
        run("git", "add", "-A")
        status = run("git", "status", "--porcelain").stdout.strip()
        if not status:
            log("[archive] nothing changed since the last snapshot")
            return 0
        run("git", "-c", "user.name=archive", "-c", "user.email=archive@souls.earth",
            "commit", "-q", "-m",
            "Snapshot %s — %d accounts" % (snapshot["date"], snapshot["accounts_total"]))
        pushed = run("git", "push", "-q", "origin", "HEAD")
        log("[archive] " + ("pushed" if pushed.returncode == 0 else
                            "committed locally; add a remote to push"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
