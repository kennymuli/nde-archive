#!/usr/bin/env python3
"""Collect the LLM extraction batches into one labels file for the census.

Reads the workflow journal rather than a tool result, so it works after a resume
and does not depend on any single run completing. Cached replays appear more than
once in the journal and are de-duplicated by their agent key.

Verifies coverage against the sampling manifest and reports any narrative the
extraction missed, since a silently short sample would bias every rate it feeds.
"""

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACT = os.path.join(HERE, "extraction")
DEFAULT_JOURNAL = (
    "/Users/kennyli/.claude/projects/-Users-kennyli-Downloads-Projects-Creami/"
    "1750cbdf-a2db-44d2-a712-b771323a37e9/subagents/workflows/wf_255c1d2d-fb5/journal.jsonl"
)

VALID = {
    "out_of_body", "tunnel", "light", "life_review", "deceased_beings", "border",
    "ineffable", "realer_than_real", "altered_time", "total_understanding",
    "telepathy", "unconditional_love", "peace", "fear_terror", "darkness_void",
    "music_sound", "religious_figure", "garden_landscape", "reluctant_return",
    "chose_return", "no_fear_of_death",
}


def main(argv=None):
    journal = (argv or sys.argv[1:] or [DEFAULT_JOURNAL])[0]
    if not os.path.exists(journal):
        print("journal not found: %s" % journal, file=sys.stderr)
        return 1

    by_key = {}
    for line in open(journal, encoding="utf-8"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "result":
            continue
        result = entry.get("result")
        if not isinstance(result, dict) or not result.get("labels"):
            continue
        by_key[entry.get("key")] = result["labels"]

    labels = {}
    unknown = Counter()
    for batch in by_key.values():
        for item in batch:
            present = [e for e in (item.get("present") or []) if e in VALID]
            for element in (item.get("present") or []):
                if element not in VALID:
                    unknown[element] += 1
            labels[item["id"]] = {
                "id": item["id"],
                "present": sorted(set(present)),
                "uncertain": sorted(set(
                    e for e in (item.get("uncertain") or []) if e in VALID)),
            }

    expected = set()
    for name in sorted(os.listdir(EXTRACT)):
        if name.startswith("batch_") and name.endswith(".json"):
            for item in json.load(open(os.path.join(EXTRACT, name), encoding="utf-8")):
                expected.add(item["id"])

    missing = expected - set(labels)
    extra = set(labels) - expected

    with open(os.path.join(EXTRACT, "labels.json"), "w", encoding="utf-8") as handle:
        json.dump(list(labels.values()), handle, ensure_ascii=False, indent=1)

    print("agent result sets (deduped): %d" % len(by_key))
    print("narratives labelled        : %d" % len(labels))
    print("narratives sampled         : %d" % len(expected))
    print("missing (not labelled)     : %d" % len(missing))
    if extra:
        print("unexpected ids             : %d" % len(extra))
    if unknown:
        print("labels outside the schema  : %s" % dict(unknown))
    if missing:
        with open(os.path.join(EXTRACT, "missing.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(sorted(missing)) + "\n")
        print("  -> listed in extraction/missing.txt; rates are computed on what")
        print("     was labelled, so re-run the workflow to close the gap")
    print("wrote %s" % os.path.join(EXTRACT, "labels.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
