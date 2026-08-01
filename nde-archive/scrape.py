#!/usr/bin/env python3
"""Extract every story from the nderf.org, adcrf.org and oberf.org archives.

Writes one file per site. Standard library only - no pip install required.

    python3 scrape.py                    # all three sites -> ./output/*.md
    python3 scrape.py --sites nderf      # just one site
    python3 scrape.py --format txt       # plain text instead of Markdown
    python3 scrape.py --limit 25         # smoke test: 25 stories per site

Pages are cached on disk, so an interrupted run resumes without re-downloading.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ndescrape.http import Cache, Fetcher, RateLimiter  # noqa: E402
from ndescrape.runner import POOLS, SITES, crawl_site, write_site  # noqa: E402

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Extract story archives from the NDERF family of sites.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sites", default="nderf,adcrf,oberf",
        help="comma-separated subset of: nderf, adcrf, oberf (default: all)",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="page cache directory")
    parser.add_argument(
        "--format", default="md", choices=("md", "txt"), help="output format",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="only process the first N stories per site (for smoke tests)",
    )
    parser.add_argument(
        "--workers", type=int, default=2,
        help="concurrent requests per site (default 2; be kind to shared hosting)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.4,
        help="minimum seconds between requests to one server (default 0.4)",
    )
    parser.add_argument(
        "--min-words", type=int, default=25,
        help="discard entries shorter than this many words (default 25)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="write a per-site report of skipped and failed URLs",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    site_keys = [s.strip() for s in args.sites.split(",") if s.strip()]
    unknown = [s for s in site_keys if s not in SITES]
    if unknown:
        print("unknown site(s): %s" % ", ".join(unknown), file=sys.stderr)
        print("choose from: %s" % ", ".join(sorted(SITES)), file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    fetcher = Fetcher(
        cache=Cache(args.cache),
        limiter=RateLimiter(args.delay, POOLS),
        log=lambda msg: print(msg, file=sys.stderr),
    )

    def log(message):
        print(message, file=sys.stderr)

    generated_note = time.strftime("%Y-%m-%d")
    started = time.time()
    summary = []

    for site_key in site_keys:
        result = crawl_site(
            site_key, fetcher, log,
            limit=args.limit, workers=args.workers, min_words=args.min_words,
        )
        path, stats = write_site(result, args.out, args.format, generated_note)
        summary.append((site_key, path, stats, result))
        log(
            "[%s] %d stories, %s words -> %s"
            % (site_key, stats["stories"], format(stats["words"], ","), path)
        )
        if result["failures"]:
            log("[%s] %d URLs failed to fetch" % (site_key, len(result["failures"])))
        if result["skipped"]:
            log("[%s] %d URLs skipped" % (site_key, len(result["skipped"])))

        if args.report:
            report_path = os.path.join(args.out, "%s-report.txt" % site_key)
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write("attempted: %d\n" % result["attempted"])
                handle.write("written:   %d\n" % stats["stories"])
                handle.write("\n== failed (%d) ==\n" % len(result["failures"]))
                for url, reason in result["failures"]:
                    handle.write("%s\t%s\n" % (url, reason))
                handle.write("\n== skipped (%d) ==\n" % len(result["skipped"]))
                for url, reason in result["skipped"]:
                    handle.write("%s\t%s\n" % (url, reason))
            log("[%s] report -> %s" % (site_key, report_path))

    elapsed = time.time() - started
    print("\n%s" % ("=" * 62))
    print("%-8s %8s %14s  %s" % ("site", "stories", "words", "file"))
    print("-" * 62)
    total_stories = 0
    total_words = 0
    for site_key, path, stats, _ in summary:
        total_stories += stats["stories"]
        total_words += stats["words"]
        print(
            "%-8s %8d %14s  %s"
            % (site_key, stats["stories"], format(stats["words"], ","), os.path.basename(path))
        )
    print("-" * 62)
    print("%-8s %8d %14s" % ("total", total_stories, format(total_words, ",")))
    print(
        "\nfetched %d pages, %d cache hits, %d failures in %.1f min"
        % (
            fetcher.stats["fetched"], fetcher.stats["hits"],
            fetcher.stats["failed"], elapsed / 60.0,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
