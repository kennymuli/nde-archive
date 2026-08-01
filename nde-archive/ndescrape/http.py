"""Polite, resumable HTTP fetching with an on-disk cache.

Standard library only. The cache makes the whole scrape restartable: a page that
has been fetched once is never fetched again, so an interrupted run resumes
almost instantly.
"""

import gzip
import hashlib
import io
import os
import random
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import zlib

USER_AGENT = (
    "nde-archive-scraper/1.0 (personal research archive; "
    "contact via site owner; respects rate limits)"
)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class FetchError(Exception):
    """Raised when a URL could not be retrieved after all retries."""

    def __init__(self, url, reason):
        super().__init__("%s -> %s" % (url, reason))
        self.url = url
        self.reason = reason


class RateLimiter:
    """Minimum spacing between request starts, per server.

    Hosts are grouped into pools because two of these sites are not two servers:
    www.adcrf.org and www.oberf.org both resolve to 192.185.31.30. Spacing them
    per-hostname would put double the intended load on one shared-hosting box.
    """

    def __init__(self, min_interval, pools=None):
        self.min_interval = min_interval
        self.pools = pools or {}
        self._next_at = {}
        self._lock = threading.Lock()

    def wait(self, host):
        key = self.pools.get(host, host)
        while True:
            with self._lock:
                now = time.monotonic()
                earliest = self._next_at.get(key, 0.0)
                if now >= earliest:
                    self._next_at[key] = now + self.min_interval
                    return
                sleep_for = earliest - now
            time.sleep(sleep_for)


class Cache:
    """Content-addressed page cache on disk."""

    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, url):
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        bucket = os.path.join(self.root, digest[:2])
        return os.path.join(bucket, digest + ".html")

    def get(self, url):
        path = self._path(url)
        try:
            with open(path, "rb") as handle:
                return handle.read().decode("utf-8")
        except (IOError, OSError):
            return None

    def put(self, url, text):
        path = self._path(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp%d" % os.getpid()
        with open(tmp, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.replace(tmp, path)


def _decompress(raw, encoding):
    if not encoding:
        return raw
    encoding = encoding.lower()
    if encoding == "gzip":
        try:
            return gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except (IOError, OSError, EOFError, zlib.error):
            return raw
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                return raw
    return raw


_CHARSET_HEADER_RE = re.compile(r"charset\s*=\s*[\"']?([\w\-]+)", re.I)
_CHARSET_META_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I
)


def decode_body(raw, content_type):
    """Decode bytes to str, trusting real signals and degrading gracefully.

    These sites span three decades of hand-authored HTML: some pages declare
    UTF-8, some declare windows-1252, and some declare nothing while actually
    containing cp1252 smart quotes. Getting this wrong produces mojibake in the
    middle of otherwise clean narrative text, so the order matters.
    """
    declared = []
    if content_type:
        found = _CHARSET_HEADER_RE.search(content_type)
        if found:
            declared.append(found.group(1))
    meta = _CHARSET_META_RE.search(raw[:4096])
    if meta:
        try:
            declared.append(meta.group(1).decode("ascii"))
        except UnicodeDecodeError:
            pass

    for name in declared:
        normalized = name.strip().lower()
        # These sites frequently mislabel cp1252 bytes as iso-8859-1. cp1252 is a
        # superset over the 0x80-0x9F range, so it is the safer reading of the two.
        if normalized in ("iso-8859-1", "latin-1", "latin1", "iso8859-1", "ascii"):
            normalized = "cp1252"
        try:
            return raw.decode(normalized)
        except (UnicodeDecodeError, LookupError):
            continue

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace")


class Fetcher:
    def __init__(self, cache, limiter, timeout=30.0, max_retries=4, log=None):
        self.cache = cache
        self.limiter = limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.log = log or (lambda msg: None)
        self._ssl_ctx = ssl.create_default_context()
        self.stats = {"hits": 0, "fetched": 0, "failed": 0, "retries": 0}
        self._stats_lock = threading.Lock()

    def _bump(self, key, amount=1):
        with self._stats_lock:
            self.stats[key] += amount

    def get(self, url, use_cache=True):
        if use_cache:
            cached = self.cache.get(url)
            if cached is not None:
                self._bump("hits")
                return cached

        # Archive pages link filenames containing literal spaces and non-ASCII
        # characters (blazenko_..., maria_...). urllib rejects both outright, so
        # percent-encode the path before requesting it.
        split = urllib.parse.urlsplit(url)
        url = urllib.parse.urlunsplit(
            split._replace(path=urllib.parse.quote(split.path, safe="/%"))
        )
        host = split.netloc
        last_reason = "unknown"

        for attempt in range(self.max_retries + 1):
            if attempt:
                # Exponential backoff with jitter, so parallel workers that hit the
                # same 503 do not retry in lockstep.
                delay = min(30.0, 2.0 ** attempt) + random.uniform(0, 1.0)
                time.sleep(delay)
                self._bump("retries")

            self.limiter.wait(host)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "close",
                },
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout, context=self._ssl_ctx
                ) as response:
                    raw = _decompress(
                        response.read(), response.headers.get("Content-Encoding")
                    )
                    text = decode_body(raw, response.headers.get("Content-Type"))
                    if use_cache:
                        self.cache.put(url, text)
                    self._bump("fetched")
                    return text
            except urllib.error.HTTPError as exc:
                last_reason = "HTTP %d" % exc.code
                if exc.code == 404:
                    break
                if exc.code not in RETRY_STATUS:
                    break
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        time.sleep(min(120, int(retry_after)))
            except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError) as exc:
                last_reason = "%s: %s" % (type(exc).__name__, exc)
            except Exception as exc:  # noqa: BLE001 - never let one page kill the run
                last_reason = "%s: %s" % (type(exc).__name__, exc)

        self._bump("failed")
        raise FetchError(url, last_reason)
