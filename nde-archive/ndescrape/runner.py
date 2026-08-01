"""Crawl orchestration: discover URLs, fetch in parallel, extract, write one file."""

import hashlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import htmltext
from .http import FetchError
from .record import write_collection
from .sites import adcrf, nderf, oberf

SITES = {
    adcrf.SITE_KEY: adcrf,
    nderf.SITE_KEY: nderf,
    oberf.SITE_KEY: oberf,
}

# adcrf.org and oberf.org resolve to the same physical server (192.185.31.30), so
# they share one concurrency budget. Hammering them as if they were two
# independent hosts would double the load on a single shared-hosting box.
POOLS = {
    "www.nderf.org": "nderf-static",
    "search.nderf.org": "nderf-search",
    "www.adcrf.org": "hostgator-shared",
    "www.oberf.org": "hostgator-shared",
}

HOSTGATOR_404_RE = re.compile(r"<title>404 - PAGE NOT FOUND</title>", re.I)
NOT_ACCEPTABLE_RE = re.compile(r"<title>Not Acceptable!</title>", re.I)


class Progress:
    def __init__(self, total, label, stream=sys.stderr):
        self.total = total
        self.label = label
        self.done = 0
        self.stream = stream
        self.started = time.time()
        self.lock = threading.Lock()

    def tick(self, note=""):
        with self.lock:
            self.done += 1
            elapsed = time.time() - self.started
            rate = self.done / elapsed if elapsed > 0 else 0
            remaining = (self.total - self.done) / rate if rate > 0 else 0
            self.stream.write(
                "\r  %s %d/%d (%.1f/s, ~%s left) %-28s"
                % (
                    self.label,
                    self.done,
                    self.total,
                    rate,
                    _duration(remaining),
                    note[:28],
                )
            )
            self.stream.flush()

    def finish(self):
        self.stream.write("\n")
        self.stream.flush()


def _duration(seconds):
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % (seconds // 60, seconds % 60)
    return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)


def _looks_like_error_page(markup):
    head = markup[:3000]
    return bool(HOSTGATOR_404_RE.search(head) or NOT_ACCEPTABLE_RE.search(head))


def crawl_site(site_key, fetcher, log, limit=None, workers=2, min_words=25):
    module = SITES[site_key]
    log("[%s] discovering story URLs" % site_key)

    def fetch(url):
        markup = fetcher.get(url)
        if _looks_like_error_page(markup):
            raise FetchError(url, "server error page")
        return markup

    urls = module.discover(fetch, log)
    if limit:
        urls = urls[:limit]
        log("  (limited to %d for this run)" % len(urls))

    docs = {}
    if site_key == nderf.SITE_KEY:
        log("  consulting search API for metadata")
        try:
            api_docs = module.fetch_index(fetch, log)
            for doc in api_docs.values():
                url = doc.get("URL") or ""
                if "/Experiences/" in url:
                    docs[module._slug_key(url)] = doc
            log("  matched %d API records to archive slugs" % len(docs))
        except Exception as exc:  # noqa: BLE001 - enrichment is optional
            log("  ! API enrichment unavailable (%s)" % exc)

    stories = []
    failures = []
    skipped = []
    seen_hashes = {}
    lock = threading.Lock()
    progress = Progress(len(urls), "fetch")

    def handle(url):
        try:
            markup = fetch(url)
        except FetchError as exc:
            with lock:
                failures.append((url, str(exc.reason)))
            progress.tick("fail")
            return
        try:
            if site_key == nderf.SITE_KEY:
                parsed = module.parse(url, markup, docs.get(module._slug_key(url)))
            else:
                parsed = module.parse(url, markup)
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the run
            with lock:
                failures.append((url, "parse error: %s" % exc))
            progress.tick("parse-err")
            return

        if isinstance(parsed, dict) and "redirect" in parsed:
            with lock:
                skipped.append((url, "redirect stub -> %s" % parsed["redirect"]))
            progress.tick("redirect")
            return
        if parsed is None:
            with lock:
                skipped.append((url, "no narrative found"))
            progress.tick("skip")
            return
        if not parsed.is_substantive(min_words):
            with lock:
                skipped.append((url, "too short (%d words)" % parsed.word_count))
            progress.tick("short")
            return

        # Some stories are published at more than one slug; keep the first.
        fingerprint = hashlib.sha256(
            re.sub(r"\W+", " ", parsed.body.lower()).strip().encode("utf-8")
        ).hexdigest()
        with lock:
            if fingerprint in seen_hashes:
                skipped.append((url, "duplicate of %s" % seen_hashes[fingerprint]))
                progress.tick("dup")
                return
            seen_hashes[fingerprint] = url
            stories.append(parsed)
        progress.tick("ok")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(handle, urls))
    progress.finish()

    stories.sort(key=lambda story: (story.title.lower(), story.url))
    return {
        "site": site_key,
        "module": module,
        "stories": stories,
        "failures": failures,
        "skipped": skipped,
        "attempted": len(urls),
    }


def write_site(result, out_dir, fmt, generated_note):
    module = result["module"]
    path = "%s/%s.%s" % (out_dir.rstrip("/"), result["site"], fmt)
    stats = write_collection(
        path,
        module.SITE_TITLE,
        module.SITE_URL,
        result["stories"],
        fmt,
        generated_note,
    )
    return path, stats
