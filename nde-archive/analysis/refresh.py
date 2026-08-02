#!/usr/bin/env python3
"""Daily incremental check for new accounts, and the currency stamp on the site.

Designed to run unattended. It does NOT re-scrape the corpus: it fetches only the
index pages, diffs the URLs against a stored manifest, and reports what is new.
A full crawl takes about an hour; this takes under a minute.

The extracted corpus is deliberately not in version control, so this writes two
small artefacts instead:

    analysis/manifest.json   every story URL seen, with the date first observed
    docs/index.html          the "archive read through" line, rewritten in place

Usage:
    python3 analysis/refresh.py              # check, update manifest and stamp
    python3 analysis/refresh.py --dry-run    # report only, write nothing
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)

from ndescrape.http import Cache, Fetcher, FetchError, RateLimiter  # noqa: E402
from ndescrape.runner import POOLS, _looks_like_error_page  # noqa: E402
from ndescrape.sites import adcrf, nderf, oberf  # noqa: E402

MANIFEST = os.path.join(HERE, "manifest.json")
PAGES = [
    os.path.join(REPO, "docs", "index.html"),
    os.path.join(ROOT, "site", "index.html"),
]

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def pretty(d):
    return "%d %s %d" % (d.day, MONTHS[d.month - 1], d.year)


def discover_all(log):
    """Every story URL the three archives currently link to."""
    fetcher = Fetcher(
        cache=Cache(os.path.join(ROOT, ".cache")),
        limiter=RateLimiter(0.4, POOLS),
        log=lambda m: None,
    )

    def fetch(url):
        # Index pages must be fetched fresh or a daily job would never see a
        # newly published account.
        markup = fetcher.get(url, use_cache=False)
        if _looks_like_error_page(markup):
            raise FetchError(url, "server error page")
        return markup

    found = {}
    for module in (nderf, adcrf, oberf):
        try:
            urls = module.discover(fetch, lambda m: None)
            found[module.SITE_KEY] = sorted(urls)
            log("  %-6s %d story URLs" % (module.SITE_KEY, len(urls)))
        except Exception as exc:  # noqa: BLE001 - one archive must not stop the rest
            log("  ! %s discovery failed: %s" % (module.SITE_KEY, exc))
            found[module.SITE_KEY] = None
    return found


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as handle:
            return json.load(handle)
    return {"first_seen": {}, "history": []}


def stamp_pages(accounts, checked, latest, log):
    """Rewrite the currency line wherever it appears."""
    touched = 0
    for path in PAGES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            html = handle.read()
        before = html
        html = re.sub(r'(<b data-field="extracted">)[^<]*(</b>)',
                      r"\g<1>%s\g<2>" % checked, html)
        html = re.sub(r'(<b data-field="accounts">)[^<]*(</b>)',
                      r"\g<1>%s\g<2>" % format(accounts, ","), html)
        if latest:
            html = re.sub(r'(<b data-field="latest">)[^<]*(</b>)',
                          r"\g<1>%s\g<2>" % latest, html)
        if html != before:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(html)
            touched += 1
            log("  stamped %s" % os.path.relpath(path, REPO))
    return touched


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    log = lambda m: print(m, flush=True)

    today = date.today()
    log("[refresh] %s" % today.isoformat())

    found = discover_all(log)
    if all(v is None for v in found.values()):
        log("[refresh] every archive unreachable - leaving the manifest untouched")
        return 1

    manifest = load_manifest()
    first_seen = manifest.get("first_seen", {})
    new = []
    total = 0
    for site, urls in found.items():
        if urls is None:
            # Never treat an unreachable archive as an empty one: that would
            # record its whole catalogue as "new" on the following run.
            total += sum(1 for u in first_seen if first_seen[u]["site"] == site)
            continue
        total += len(urls)
        for url in urls:
            if url not in first_seen:
                first_seen[url] = {"site": site, "seen": today.isoformat()}
                new.append((site, url))

    log("[refresh] %d story URLs across the archives; %d new since last check"
        % (total, len(new)))
    for site, url in new[:20]:
        log("    + %-6s %s" % (site, url.rsplit("/", 1)[-1]))
    if len(new) > 20:
        log("    ... and %d more" % (len(new) - 20))

    if args.dry_run:
        log("[refresh] dry run - nothing written")
        return 0

    manifest["first_seen"] = first_seen
    manifest.setdefault("history", []).append(
        {"date": today.isoformat(), "total": total, "new": len(new)})
    manifest["history"] = manifest["history"][-400:]
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)

    latest = None
    data = os.path.join(HERE, "data", "nderf.jsonl")
    if os.path.exists(data):
        dates = []
        for line in open(data, encoding="utf-8"):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("submit_date"):
                dates.append(record["submit_date"][:10])
        if dates:
            latest = pretty(datetime.strptime(max(dates), "%Y-%m-%d").date())

    stamp_pages(total, pretty(today), latest, log)
    log("[refresh] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
