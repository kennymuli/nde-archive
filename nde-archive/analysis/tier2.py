#!/usr/bin/env python3
"""Tier 2: cross-tabs, transitions, co-occurrence, and the expectancy test.

Sections
    I66  religion before -> after, as two separate variables
    J78  element rates by gender
    J79  element rates by age at experience
    B12  element co-occurrence (lift over independence)
    J83  do people who already knew about NDEs report more canonical accounts?

Rates carry Wilson 95% intervals. Where many comparisons are made at once the
report says so, because with ~20 elements across several subgroups a handful of
"significant" differences are expected from noise alone.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import option_coding  # noqa: E402
from census import LLM_ELEMENTS, PROMPTED, load, wilson  # noqa: E402

EXTRACT = os.path.join(HERE, "extraction")

RELIGION_PRIOR = "What was your religion prior to your experience?"
RELIGION_NOW = "What is your religion now?"
PRIOR_KNOWLEDGE = "Did you have any knowledge of near death experience (NDE) prior to your experience?"
GENDER_Q = "Gender"

# The instrument changed: older forms asked for a denomination, newer ones asked
# for religiosity AND denomination and stored the two concatenated ("Moderate
# Christian", "Liberal none"). Treating the raw string as one categorical
# variable yields 2,166 "categories" and a meaningless transition matrix, so the
# two axes are separated here and reported independently.
INTENSITY = ["conservative/fundamentalist", "conservative", "moderate", "liberal"]

DENOM_MAP = [
    (r"catholic", "Christian - Catholic"),
    (r"protestant|baptist|methodist|lutheran|presbyterian|episcopal|anglican|pentecostal", "Christian - Protestant"),
    (r"mormon|latter.day", "Christian - LDS"),
    (r"orthodox", "Christian - Orthodox"),
    (r"jehovah", "Christian - Jehovah's Witness"),
    (r"other christian|^christian$|christian\b", "Christian - Other"),
    (r"jewish|judaism", "Jewish"),
    (r"muslim|islam", "Muslim"),
    (r"buddhis", "Buddhist"),
    (r"hindu", "Hindu"),
    (r"atheist", "Unaffiliated - Atheist"),
    (r"agnostic", "Unaffiliated - Agnostic"),
    (r"nothing in particular|unaffiliated|secular|none\b|^no religion", "Unaffiliated - None"),
    (r"new age|pagan|wicca|spiritualist|shaman", "Other - New age/Pagan"),
    (r"several faiths|other or several|other faith", "Other or several faiths"),
    (r"spiritual", "Spiritual, not religious"),
]

MISSING_RELIGION = re.compile(
    r"^(no comment|no response|do not know|don'?t know|n/?a|none given|unknown)\b", re.I)


def parse_religion(raw):
    """Return (intensity, denomination); either may be None."""
    text = (raw or "").strip().lower()
    text = re.sub(r"\s+", " ", text.replace("-", " ").replace("/", "/"))
    if not text or MISSING_RELIGION.match(text):
        return None, None

    intensity = None
    for level in INTENSITY:
        probe = level.replace("/", "/")
        if text.startswith(probe):
            intensity = level.split("/")[0].capitalize()
            text = text[len(probe):].strip()
            break

    if not text:
        return intensity, None
    for pattern, label in DENOM_MAP:
        if re.search(pattern, text):
            return intensity, label
    return intensity, None


def answer(record, label):
    item = record["answers"].get(label)
    return item["raw"] if item else None


def rate_line(name, hits, total, width=26):
    if not total:
        return "%-*s %8s" % (width, name, "-")
    low, high = wilson(hits, total)
    return "%-*s %6.1f%% [%4.1f-%4.1f] n=%-5d" % (
        width, name, 100.0 * hits / total, 100 * low, 100 * high, total)


def two_proportion_z(h1, n1, h2, n2):
    """Z test for a difference in proportions; None when either cell is thin."""
    if min(n1, n2) < 30 or not n1 or not n2:
        return None
    p1, p2 = h1 / n1, h2 / n2
    pooled = (h1 + h2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    return (p1 - p2) / se


def section(title):
    return ["", "=" * 80, title, "=" * 80]


def load_spontaneous():
    path = os.path.join(EXTRACT, "labels.json")
    if not os.path.exists(path):
        return {}
    return {i["id"]: set(i.get("present") or [])
            for i in json.load(open(path, encoding="utf-8"))}


def record_id(record):
    return "%s::%s" % (record["site"], record["url"].rsplit("/", 1)[-1])


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    nderf = load("nderf")
    spontaneous = load_spontaneous()
    out = []

    # ---- I66 religion transition ------------------------------------------
    out += section("I66. RELIGION BEFORE -> AFTER")
    out.append("The item's answers combine two axes; they are separated here.")

    intensity_pairs = Counter()
    denom_pairs = Counter()
    for record in nderf:
        before_i, before_d = parse_religion(answer(record, RELIGION_PRIOR))
        after_i, after_d = parse_religion(answer(record, RELIGION_NOW))
        if before_i and after_i:
            intensity_pairs[(before_i, after_i)] += 1
        if before_d and after_d:
            denom_pairs[(before_d, after_d)] += 1

    levels = ["Liberal", "Moderate", "Conservative"]
    total_i = sum(intensity_pairs.values())
    out.append("")
    out.append("RELIGIOSITY (n=%d pairs).  rows = before, cols = after, %% of row" % total_i)
    out.append("%-16s %10s %10s %10s %8s" % ("", *levels, "n"))
    for before in levels:
        row_total = sum(intensity_pairs[(before, a)] for a in levels)
        cells = "".join("%10s" % (
            "%.1f%%" % (100.0 * intensity_pairs[(before, a)] / row_total) if row_total else "-")
            for a in levels)
        out.append("%-16s%s %8d" % (before, cells, row_total))
    stayed = sum(intensity_pairs[(x, x)] for x in levels)
    if total_i:
        out.append("unchanged: %.1f%%" % (100.0 * stayed / total_i))

    total_d = sum(denom_pairs.values())
    denoms = [d for d, _ in Counter(
        b for (b, a), n in denom_pairs.items() for _ in range(n)).most_common(9)]
    out.append("")
    out.append("DENOMINATION (n=%d pairs). %% of row that ended in each column" % total_d)
    out.append("%-30s %8s %8s %8s" % ("before", "stayed", "-> None", "n"))
    for denom in denoms:
        row_total = sum(n for (b, a), n in denom_pairs.items() if b == denom)
        if row_total < 20:
            continue
        stayed_n = denom_pairs[(denom, denom)]
        to_none = sum(n for (b, a), n in denom_pairs.items()
                      if b == denom and a.startswith("Unaffiliated"))
        out.append("%-30s %7.1f%% %7.1f%% %8d" % (
            denom, 100.0 * stayed_n / row_total, 100.0 * to_none / row_total, row_total))
    net = Counter()
    for (b, a), n in denom_pairs.items():
        net[a] += n
        net[b] -= n
    out.append("")
    out.append("net change by category (positive = gained adherents)")
    for label, delta in sorted(net.items(), key=lambda kv: -kv[1])[:6]:
        out.append("   %-32s %+5d" % (label, delta))
    for label, delta in sorted(net.items(), key=lambda kv: kv[1])[:3]:
        out.append("   %-32s %+5d" % (label, delta))

    # ---- J78 / J79 element rates by subgroup -------------------------------
    def prompted_flag(record, element):
        labels = PROMPTED.get(element)
        if not labels:
            return None
        for label in labels:
            if label in record["answers"]:
                verdict = option_coding.classify(element, record["answers"][label]["raw"])
                if verdict in ("affirmative", "partial"):
                    return True
                if verdict == "negative":
                    return False
                return None
        return None

    def subgroup_table(title, key_fn, order, min_n=60):
        rows = section(title)
        groups = defaultdict(list)
        for record in nderf:
            key = key_fn(record)
            if key:
                groups[key].append(record)
        keys = [k for k in order if len(groups.get(k, [])) >= min_n]
        if not keys:
            return rows + ["insufficient data"]
        rows.append("prompted affirmative rate, by subgroup (n in header)")
        rows.append("%-22s%s" % ("element", "".join(
            "%16s" % ("%s(%d)" % (k[:9], len(groups[k]))) for k in keys)))
        rows.append("-" * 80)
        for element in PROMPTED:
            cells = ""
            values = []
            for key in keys:
                flags = [prompted_flag(r, element) for r in groups[key]]
                flags = [f for f in flags if f is not None]
                if len(flags) < 30:
                    cells += "%16s" % "-"
                    values.append(None)
                    continue
                hits = sum(flags)
                cells += "%15.1f%%" % (100.0 * hits / len(flags))
                values.append((hits, len(flags)))
            mark = ""
            valid = [v for v in values if v]
            if len(valid) >= 2:
                z = two_proportion_z(valid[0][0], valid[0][1], valid[-1][0], valid[-1][1])
                if z is not None and abs(z) > 2.58:
                    mark = "  **"
                elif z is not None and abs(z) > 1.96:
                    mark = "  *"
            rows.append("%-22s%s%s" % (element, cells, mark))
        rows.append("")
        rows.append("* p<0.05, ** p<0.01 comparing first and last column only.")
        rows.append("With %d elements tested, expect ~1 false positive at p<0.05 by chance."
                    % len(PROMPTED))
        return rows

    def gender_of(record):
        raw = answer(record, GENDER_Q)
        if not raw:
            return None
        text = raw.strip().lower()
        if text.startswith("female") or text.startswith("femail"):
            return "Female"
        if text.startswith("male"):
            return "Male"
        return None

    out += subgroup_table("J78. ELEMENT RATES BY GENDER", gender_of, ["Female", "Male"])

    AGE_ORDER = ["Baby", "Toddler", "Young Child", "Older Child", "College Age",
                 "Adult", "Older"]
    out += subgroup_table("J79. ELEMENT RATES BY AGE AT EXPERIENCE",
                          lambda r: r.get("age_bucket"), AGE_ORDER)

    # ---- B12 co-occurrence -------------------------------------------------
    if spontaneous:
        out += section("B12. ELEMENT CO-OCCURRENCE (spontaneous labels, n=%d)"
                       % len(spontaneous))
        out.append("lift = P(both) / (P(a) * P(b)). >1 means they travel together.")
        sets = list(spontaneous.values())
        total = len(sets)
        single = {e: sum(1 for s in sets if e in s) / total for e in LLM_ELEMENTS}
        lifts = []
        for i, a in enumerate(LLM_ELEMENTS):
            for b in LLM_ELEMENTS[i + 1:]:
                both = sum(1 for s in sets if a in s and b in s) / total
                if both < 0.01 or not single[a] or not single[b]:
                    continue
                lifts.append((both / (single[a] * single[b]), a, b, both))
        lifts.sort(reverse=True)
        out.append("")
        out.append("strongest positive associations")
        out.append("%-24s %-24s %7s %8s" % ("element A", "element B", "lift", "co-occur"))
        for lift, a, b, both in lifts[:12]:
            out.append("%-24s %-24s %7.2f %7.1f%%" % (a, b, lift, 100 * both))
        out.append("")
        out.append("weakest (elements that avoid each other)")
        for lift, a, b, both in lifts[-6:]:
            out.append("%-24s %-24s %7.2f %7.1f%%" % (a, b, lift, 100 * both))

        # element count distribution
        counts = sorted(len(s) for s in sets)
        out.append("")
        out.append("elements reported per narrative: median=%d  p25=%d  p75=%d  max=%d"
                   % (counts[len(counts) // 2], counts[len(counts) // 4],
                      counts[3 * len(counts) // 4], counts[-1]))
        out.append("narratives with zero elements: %d (%.1f%%)"
                   % (counts.count(0), 100.0 * counts.count(0) / total))

    # ---- J83 expectancy ----------------------------------------------------
    out += section("J83. PRIOR NDE KNOWLEDGE vs ACCOUNT CONTENT")
    out.append("Does knowing about NDEs beforehand predict a more canonical account?")
    out.append("This is the corpus's own test of an expectancy effect.")

    groups = {"knew": [], "did not know": []}
    for record in nderf:
        raw = answer(record, PRIOR_KNOWLEDGE)
        if not raw:
            continue
        verdict = option_coding.classify("prior_knowledge", raw)
        if verdict == "affirmative":
            groups["knew"].append(record)
        elif verdict == "negative":
            groups["did not know"].append(record)

    out.append("")
    out.append("group sizes: knew=%d, did not know=%d"
               % (len(groups["knew"]), len(groups["did not know"])))
    if min(len(v) for v in groups.values()) >= 30:
        out.append("")
        out.append("%-22s %14s %14s %8s" % ("element", "knew", "did not know", "z"))
        out.append("-" * 62)
        for element in PROMPTED:
            cells = {}
            for name, records in groups.items():
                flags = [prompted_flag(r, element) for r in records]
                flags = [f for f in flags if f is not None]
                cells[name] = (sum(flags), len(flags))
            if min(n for _, n in cells.values()) < 30:
                continue
            z = two_proportion_z(*cells["knew"], *cells["did not know"])
            out.append("%-22s %13.1f%% %13.1f%% %8s" % (
                element,
                100.0 * cells["knew"][0] / cells["knew"][1],
                100.0 * cells["did not know"][0] / cells["did not know"][1],
                "-" if z is None else "%+.2f" % z))

        # spontaneous element count, which prompting cannot inflate
        if spontaneous:
            out.append("")
            out.append("spontaneous elements per narrative (prompting-free measure)")
            for name, records in groups.items():
                counts = [len(spontaneous[record_id(r)]) for r in records
                          if record_id(r) in spontaneous]
                if len(counts) >= 20:
                    counts.sort()
                    out.append("   %-14s n=%-4d median=%d  mean=%.2f"
                               % (name, len(counts), counts[len(counts) // 2],
                                  sum(counts) / len(counts)))
                else:
                    out.append("   %-14s n=%-4d (too few sampled for a stable estimate)"
                               % (name, len(counts)))
    else:
        out.append("one group is too small for a stable comparison")

    text = "\n".join(out)
    with open(os.path.join(HERE, "tier2.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
