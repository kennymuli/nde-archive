#!/usr/bin/env python3
"""Tier 1: the element census and baseline counts.

Reports PROMPTED rates (from the questionnaire, full corpus) beside SPONTANEOUS
rates (from LLM extraction on the 1,500-narrative sample) without ever merging
them. They answer different questions:

  prompted    - when asked directly, what share said yes
  spontaneous - when writing freely, what share described it unbidden

The gap between them is the interesting quantity, which is precisely why the two
must not be summed or averaged.

Usage:
    python3 analysis/census.py
    python3 analysis/census.py --no-spontaneous     # prompted only
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

import option_coding

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "data")
EXTRACT = os.path.join(HERE, "extraction")
SITES = ("nderf", "adcrf", "oberf")

# One element maps to several question wordings: the questionnaire was revised
# over time and each site phrases things differently. Collapsing the variants is
# required, but the denominators must stay per-variant-union or the rate is
# computed against people who were never asked.
PROMPTED = OrderedDict([
    ("out_of_body", [
        "Did you feel separated from your body?",
        "Did you experience a separation of your consciousness from your body?",
    ]),
    ("tunnel", [
        "Did you pass into or through a tunnel?",
        "Did you pass into or through a tunnel or enclosure?",
    ]),
    ("light", [
        "Did you see an unearthly light?",
        "Did you see, or feel surrounded by, a brilliant light?",
        "Did you see a light?",
    ]),
    ("life_review", [
        "Did scenes from your past come back to you?",
        "Did scenes from your past come back?",
    ]),
    ("deceased_beings", [
        "Did you encounter or become aware of any deceased (or alive) beings?",
        "Did you see the deceased?",
    ]),
    ("border", ["Did you come to a border or point of no return?"]),
    ("ineffable", [
        "Was the experience difficult to express in words?",
        "Was the kind of experience difficult to express in words?",
        "Was this experience difficult to express in words?",
    ]),
    ("altered_time", ["Did you time seem to speed up or slow down?",
                      "Did time seem to speed up or slow down?"]),
    ("total_understanding", [
        "Did you suddenly seem to understand everything?",
        "Did you suddenly understand everything?",
    ]),
    ("unearthly_world", ["Did you seem to enter some other, unearthly world?"]),
    ("future_scenes", ["Did scenes from the future come to you?"]),
    ("psychic_after", [
        "Do you have any psychic, non-ordinary or other special gifts after your experience that you did not have before the experience?",
        "Did you have any psychic, paranormal or other special gifts following the experience that you did not have prior to the experience?",
    ]),
    ("values_changed", [
        "Did you have a change in your values and beliefs because of your experience?",
    ]),
])

# The 21 elements the LLM extraction labels. Those with no PROMPTED entry were
# never asked about by the questionnaire - see the "unasked" section of the
# report, which is where genuinely new content is most likely to surface.
LLM_ELEMENTS = [
    "out_of_body", "tunnel", "light", "life_review", "deceased_beings", "border",
    "ineffable", "realer_than_real", "altered_time", "total_understanding",
    "telepathy", "unconditional_love", "peace", "fear_terror", "darkness_void",
    "music_sound", "religious_figure", "garden_landscape", "reluctant_return",
    "chose_return", "no_fear_of_death",
]

# Per-element recall of the retired regex lexicon, from the 80-narrative
# validation. Retained only so the report can state why regex output is not used.
REGEX_RECALL = {
    "out_of_body": 0.43, "tunnel": 0.88, "light": 0.75, "life_review": 0.12,
    "deceased_beings": 0.27, "border": 0.00, "ineffable": 0.59,
    "realer_than_real": 0.33, "altered_time": 0.20, "total_understanding": 0.38,
    "telepathy": 0.48, "unconditional_love": 0.33, "peace": 0.04,
    "fear_terror": 0.25, "darkness_void": 0.32, "music_sound": 0.44,
    "religious_figure": 0.93, "garden_landscape": 0.40, "reluctant_return": 0.17,
    "chose_return": 0.00, "no_fear_of_death": 0.43,
}


def wilson(successes, total, z=1.96):
    """Wilson score interval - behaves sensibly near 0 and 1, unlike the normal
    approximation, which matters for the rare elements."""
    if not total:
        return None, None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def load(site):
    path = os.path.join(DATA, "%s.jsonl" % site)
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def prompted_rate(records, labels, element):
    """Affirmative share among valid responses.

    Delegates to option_coding, which knows each item's real answer vocabulary.
    Counting literal "yes" here instead reported 0.0% for every item that offers
    descriptive alternatives rather than yes/no.
    """
    counts, valid = option_coding.rate(records, labels, element)
    return counts["affirmative"], valid, counts


def load_extraction():
    """Merge the LLM extraction batches into {id: set(elements)}."""
    labels = {}
    path = os.path.join(EXTRACT, "labels.json")
    if os.path.exists(path):
        for item in json.load(open(path, encoding="utf-8")):
            labels[item["id"]] = set(item.get("present") or [])
    return labels


def section(title):
    return ["", "=" * 78, title, "=" * 78]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-spontaneous", action="store_true")
    args = parser.parse_args(argv)

    corpora = {site: load(site) for site in SITES}
    corpora = {k: v for k, v in corpora.items() if v}
    if not corpora:
        print("no prepared data - run analysis/prepare.py first", file=sys.stderr)
        return 1

    out = []
    out += section("A. CORPUS BASELINE")
    out.append("%-8s %8s %12s %10s %10s %8s" % (
        "site", "accounts", "total words", "med words", "med Qs", "no-narr"))
    for site, records in corpora.items():
        words = sorted(r["narrative_words"] for r in records)
        questions = sorted(r["n_questions"] for r in records)
        out.append("%-8s %8d %12s %10d %10d %8d" % (
            site, len(records),
            format(sum(r["narrative_words"] + r["answer_words"] for r in records), ","),
            words[len(words) // 2], questions[len(questions) // 2],
            sum(1 for w in words if w == 0)))

    # Length distribution - the tail matters, since a handful of very long
    # accounts can dominate any word-weighted statistic.
    out.append("")
    out.append("narrative length percentiles (words)")
    out.append("%-8s %6s %6s %6s %6s %6s %6s" % ("site", "p10", "p25", "p50", "p75", "p90", "max"))
    for site, records in corpora.items():
        words = sorted(r["narrative_words"] for r in records)
        pick = lambda q: words[min(len(words) - 1, int(q * len(words)))]
        out.append("%-8s %6d %6d %6d %6d %6d %6d" % (
            site, pick(.10), pick(.25), pick(.50), pick(.75), pick(.90), words[-1]))

    out += section("B. ELEMENT CENSUS - PROMPTED (questionnaire, full corpus)")
    out.append("share answering YES, among those asked. n = number asked.")
    out.append("")
    header = "%-22s" % "element"
    for site in corpora:
        header += "%18s" % site
    out.append(header)
    out.append("-" * 78)
    for element, labels in PROMPTED.items():
        row = "%-22s" % element
        for site, records in corpora.items():
            yes, asked, counts = prompted_rate(records, labels, element)
            if asked < 30:
                row += "%18s" % ("-" if not asked else "n=%d" % asked)
            else:
                mark = "+" if counts["partial"] else " "
                row += "%18s" % ("%.1f%%%s(n=%d)" % (100.0 * yes / asked, mark, asked))
        out.append(row)

    spontaneous = {} if args.no_spontaneous else load_extraction()
    if spontaneous:
        manifest = json.load(open(os.path.join(EXTRACT, "manifest.json"), encoding="utf-8"))
        weights = manifest["weights"]

        by_site = defaultdict(list)
        for key, elements in spontaneous.items():
            by_site[key.split("::")[0]].append(elements)

        out += section("B. ELEMENT CENSUS - SPONTANEOUS (free narrative, sampled)")
        out.append("share whose OWN narrative describes it, unprompted.")
        out.append("95%% CI in brackets. n per site = %s" % ", ".join(
            "%s=%d" % (s, len(v)) for s, v in by_site.items()))
        out.append("")
        header = "%-22s" % "element"
        for site in by_site:
            header += "%22s" % site
        out.append(header)
        out.append("-" * 90)
        for element in LLM_ELEMENTS:
            row = "%-22s" % element
            for site, sets in by_site.items():
                hits = sum(1 for s in sets if element in s)
                low, high = wilson(hits, len(sets))
                row += "%22s" % ("%.1f%% [%.0f-%.0f]" % (
                    100.0 * hits / len(sets), 100 * low, 100 * high))
            out.append(row)

        # The comparison this whole exercise exists to make.
        out += section("B. PROMPTED vs SPONTANEOUS (nderf)")
        out.append("A large gap means people confirm the element when asked but rarely")
        out.append("volunteer it. A small gap means it is central to how they tell the story.")
        out.append("")
        out.append("%-22s %12s %14s %10s" % ("element", "prompted", "spontaneous", "gap"))
        out.append("-" * 62)
        nderf_sets = by_site.get("nderf") or []
        for element in LLM_ELEMENTS:
            if element not in PROMPTED or not nderf_sets:
                continue
            yes, asked, _ = prompted_rate(corpora["nderf"], PROMPTED[element], element)
            if asked < 30:
                continue
            p = 100.0 * yes / asked
            hits = sum(1 for s in nderf_sets if element in s)
            s = 100.0 * hits / len(nderf_sets)
            out.append("%-22s %11.1f%% %13.1f%% %+9.1f" % (element, p, s, s - p))

        out += section("B14. ELEMENTS THE QUESTIONNAIRE NEVER ASKS ABOUT")
        out.append("Present in narratives but absent from the instrument, so no")
        out.append("prompted rate exists anywhere in the published research.")
        out.append("")
        out.append("%-22s %14s" % ("element", "spontaneous"))
        out.append("-" * 40)
        for element in LLM_ELEMENTS:
            if element in PROMPTED:
                continue
            total = sum(len(v) for v in by_site.values())
            hits = sum(1 for sets in by_site.values() for s in sets if element in s)
            out.append("%-22s %13.1f%%" % (element, 100.0 * hits / max(1, total)))

        out += section("METHOD NOTE - why spontaneous rates are not from regex")
        out.append("The regex lexicon was validated against 80 blind-labelled narratives")
        out.append("and retired: micro recall 0.40, precision 0.84, with per-element")
        out.append("recall from 0.00 to 0.93. Inter-labeller kappa was 0.96, so the")
        out.append("failure was the patterns, not the task. Worst offenders:")
        for element, recall in sorted(REGEX_RECALL.items(), key=lambda kv: kv[1])[:6]:
            out.append("    %-22s regex recall %.2f" % (element, recall))
    else:
        out += section("SPONTANEOUS RATES: not yet available")
        out.append("Run the extraction workflow, then analysis/merge_extraction.py.")

    text = "\n".join(out)
    with open(os.path.join(HERE, "census.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
