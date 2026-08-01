#!/usr/bin/env python3
"""Tier 3: sequence structure, beings, settings, claims, and style.

Aggregates the open-vocabulary extraction into:
    C19-C21  event ordering and transition probabilities
    D25-D34  who is encountered, and how
    E35-E40  where it takes place
    P125-130 corroboration claims - what is asserted, how specifically
    O116-119 ineffability, tense shift, self-reference
    Q131-132 narratives that fit no common pattern

Everything here is descriptive. Claims are counted and characterised, never
adjudicated.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TIER3 = os.path.join(HERE, "tier3")
sys.path.insert(0, HERE)

EVENTS = [
    "crisis", "separation", "viewing_body", "transit", "darkness", "light",
    "being_encounter", "realm_arrival", "life_review", "knowledge", "message",
    "border", "decision", "forced_return", "reentry", "aftermath",
]

JOURNALS = [
    "/Users/kennyli/.claude/projects/-Users-kennyli-Downloads-Projects-Creami/"
    "1750cbdf-a2db-44d2-a712-b771323a37e9/subagents/workflows/wf_00509a98-33b/journal.jsonl",
]


def load_records():
    records = {}
    for path in JOURNALS:
        if not os.path.exists(path):
            continue
        by_key = {}
        for line in open(path, encoding="utf-8"):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "result":
                continue
            result = entry.get("result")
            if isinstance(result, dict) and result.get("records"):
                by_key[entry.get("key")] = result["records"]
        for batch in by_key.values():
            for item in batch:
                records[item["id"]] = item
    return records


def site_of(key):
    return key.split("::")[0]


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def section(title):
    return ["", "=" * 80, title, "=" * 80]


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    records = load_records()
    if not records:
        print("no tier3 records - run the extraction workflow first", file=sys.stderr)
        return 1

    out = []
    total = len(records)
    by_site = defaultdict(list)
    for key, record in records.items():
        by_site[site_of(key)].append(record)

    out += section("TIER 3 - %d narratives (%s)" % (
        total, ", ".join("%s=%d" % (s, len(v)) for s, v in sorted(by_site.items()))))

    # ---- C. sequence -------------------------------------------------------
    out += section("C19-C21. EVENT SEQUENCE")
    sequences = [r.get("sequence") or [] for r in records.values()]
    lengths = sorted(len(s) for s in sequences)
    out.append("events per narrative: median=%d p25=%d p75=%d max=%d; %d have none"
               % (lengths[len(lengths) // 2], lengths[len(lengths) // 4],
                  lengths[3 * len(lengths) // 4], lengths[-1], lengths.count(0)))

    first = Counter(s[0] for s in sequences if s)
    last = Counter(s[-1] for s in sequences if s)
    out.append("")
    out.append("%-20s %10s %10s" % ("event", "opens %", "closes %"))
    for event in EVENTS:
        opens, closes = first.get(event, 0), last.get(event, 0)
        if opens or closes:
            out.append("%-20s %9.1f%% %9.1f%%" % (
                event, pct(opens, sum(first.values())), pct(closes, sum(last.values()))))

    # Transition probabilities: P(next | current), the empirical grammar.
    transitions = defaultdict(Counter)
    for sequence in sequences:
        for a, b in zip(sequence, sequence[1:]):
            transitions[a][b] += 1
    out.append("")
    out.append("most likely NEXT event, given the current one")
    out.append("%-20s %-20s %8s %8s" % ("from", "most likely next", "P", "n"))
    for event in EVENTS:
        row = transitions.get(event)
        if not row or sum(row.values()) < 15:
            continue
        nxt, count = row.most_common(1)[0]
        out.append("%-20s %-20s %7.0f%% %8d" % (
            event, nxt, pct(count, sum(row.values())), sum(row.values())))

    # How ordered is the corpus? Compare each pair's observed order consistency.
    out.append("")
    out.append("ordering consistency: of narratives containing BOTH events,")
    out.append("the share where the first listed precedes the second")
    pairs = []
    for i, a in enumerate(EVENTS):
        for b in EVENTS[i + 1:]:
            ab = ba = 0
            for sequence in sequences:
                if a in sequence and b in sequence:
                    if sequence.index(a) < sequence.index(b):
                        ab += 1
                    else:
                        ba += 1
            if ab + ba >= 25:
                pairs.append((max(ab, ba) / (ab + ba), a, b, ab, ba, ab + ba))
    pairs.sort(reverse=True)
    out.append("%-20s %-20s %10s %6s" % ("event A", "event B", "consistency", "n"))
    for score, a, b, ab, ba, n in pairs[:10]:
        direction = "%s -> %s" % (a, b) if ab >= ba else "%s -> %s" % (b, a)
        out.append("%-41s %9.0f%% %6d" % (direction, 100 * score, n))
    if pairs:
        out.append("")
        out.append("least consistent (order varies most)")
        for score, a, b, ab, ba, n in pairs[-4:]:
            out.append("%-20s %-20s %9.0f%% %6d" % (a, b, 100 * score, n))

    # ---- D. beings ---------------------------------------------------------
    out += section("D25-D34. BEINGS ENCOUNTERED")
    beings = [b for r in records.values() for b in (r.get("beings") or [])]
    with_beings = sum(1 for r in records.values() if r.get("beings"))
    out.append("narratives reporting at least one being: %d (%.1f%%)"
               % (with_beings, pct(with_beings, total)))
    out.append("total beings mentioned: %d" % len(beings))

    def canon(who):
        text = (who or "").lower().strip()
        for pattern, label in [
            (r"grandmother|grandma|grandpa|grandfather|grandparent", "deceased grandparent"),
            (r"mother|father|mom|dad|parent", "deceased parent"),
            (r"brother|sister|sibling", "sibling"),
            (r"son|daughter|child", "child"),
            (r"husband|wife|spouse|partner", "spouse/partner"),
            (r"aunt|uncle|cousin|niece|nephew|in.law", "extended family"),
            (r"friend", "friend"),
            (r"jesus|christ", "Jesus/Christ"),
            (r"\bgod\b|father god", "God"),
            (r"angel", "angel"),
            (r"virgin mary|\bmary\b", "Mary"),
            (r"buddha|krishna|allah|muhammad", "other religious figure"),
            (r"being of light|light being|luminous", "being of light"),
            (r"guide|guardian", "guide"),
            (r"pet|dog|cat|horse|animal", "animal/pet"),
            (r"presence|entity|figure|someone|unknown|unidentified|unnamed", "unidentified presence"),
            (r"stranger|people|crowd|group|others", "strangers/others"),
            (r"living", "living person"),
        ]:
            if re.search(pattern, text):
                return label
        return "other/unspecified"

    kinds = Counter(canon(b.get("who")) for b in beings)
    out.append("")
    out.append("%-28s %8s %8s" % ("being type", "count", "% of beings"))
    for label, count in kinds.most_common(14):
        out.append("%-28s %8d %7.1f%%" % (label, count, pct(count, len(beings))))

    not_known_dead = sum(1 for b in beings if b.get("known_dead_before") == "no")
    applicable = sum(1 for b in beings
                     if b.get("known_dead_before") in ("yes", "no"))
    out.append("")
    out.append("D26. encountered someone NOT known to be dead at the time:")
    out.append("     %d of %d deceased-person encounters (%.1f%%)"
               % (not_known_dead, applicable, pct(not_known_dead, applicable)))

    communication = Counter(b.get("communication") for b in beings if b.get("communication"))
    out.append("")
    out.append("communication mode")
    for mode, count in communication.most_common():
        out.append("   %-16s %6d  %5.1f%%" % (mode, count, pct(count, sum(communication.values()))))

    # ---- E. settings -------------------------------------------------------
    out += section("E35-E40. SETTINGS")
    settings = Counter(s.lower().strip() for r in records.values()
                       for s in (r.get("settings") or []))
    with_setting = sum(1 for r in records.values() if r.get("settings"))
    out.append("narratives describing a setting: %d (%.1f%%)"
               % (with_setting, pct(with_setting, total)))
    out.append("")
    out.append("%-26s %8s" % ("setting", "% of narratives"))
    for label, count in settings.most_common(18):
        out.append("%-26s %10.1f%%" % (label, pct(count, total)))

    # ---- P. claims ---------------------------------------------------------
    out += section("P125-P130. CORROBORATION CLAIMS (descriptive only)")
    out.append("What is asserted and in what detail. Nothing here is adjudicated.")
    claims = [c for r in records.values() for c in (r.get("claims") or [])]
    with_claim = sum(1 for r in records.values() if r.get("claims"))
    out.append("")
    out.append("narratives making at least one checkable-in-principle claim: %d (%.1f%%)"
               % (with_claim, pct(with_claim, total)))
    out.append("total claims: %d" % len(claims))

    by_site_claim = {}
    for site, group in by_site.items():
        n = sum(1 for r in group if r.get("claims"))
        by_site_claim[site] = (n, len(group))
    out.append("   by corpus: " + ", ".join(
        "%s %.1f%%" % (s, pct(n, t)) for s, (n, t) in sorted(by_site_claim.items())))

    kinds = Counter(c.get("kind") for c in claims)
    out.append("")
    out.append("%-32s %8s" % ("claim kind", "count"))
    for label, count in kinds.most_common(10):
        out.append("%-32s %8d" % (label, count))

    out.append("")
    out.append("%-14s %10s %10s %10s" % ("specificity", "none", "narrator", "third party"))
    for level in ("vague", "moderate", "specific"):
        row = [c for c in claims if c.get("specificity") == level]
        counts = Counter(c.get("corroboration_asserted") for c in row)
        out.append("%-14s %10d %10d %10d" % (
            level, counts.get("none", 0), counts.get("claimed_by_narrator", 0),
            counts.get("claimed_by_third_party", 0)))
    specific_corroborated = sum(
        1 for c in claims
        if c.get("specificity") == "specific"
        and c.get("corroboration_asserted") in ("claimed_by_narrator", "claimed_by_third_party"))
    out.append("")
    out.append("specific AND with corroboration asserted: %d (%.1f%% of all claims)"
               % (specific_corroborated, pct(specific_corroborated, len(claims))))

    # ---- O. style ----------------------------------------------------------
    out += section("O116-O119. LANGUAGE AND STYLE")
    for field, labels in (
        ("ineffability", ["none", "once", "repeated"]),
        ("tense_shift", ["none", "shifts_to_present"]),
        ("self_reference", ["first_person_throughout", "refers_to_body_as_object", "mixed"]),
    ):
        counts = Counter((r.get("style") or {}).get(field) for r in records.values())
        counts.pop(None, None)
        out.append("")
        out.append("%s" % field)
        for label in labels:
            out.append("   %-30s %6d  %5.1f%%" % (
                label, counts.get(label, 0), pct(counts.get(label, 0), sum(counts.values()))))

    # Does ineffability track richness? A narrative that says it cannot be
    # described might report more, not less.
    out.append("")
    out.append("mean events reported, by ineffability level")
    for level in ("none", "once", "repeated"):
        group = [len(r.get("sequence") or []) for r in records.values()
                 if (r.get("style") or {}).get("ineffability") == level]
        if len(group) >= 20:
            out.append("   %-12s n=%-5d mean=%.2f" % (level, len(group), sum(group) / len(group)))

    # ---- messages ----------------------------------------------------------
    out += section("G54. RECURRING MESSAGE THEMES")
    messages = [m.lower() for r in records.values() for m in (r.get("messages") or [])]
    out.append("narratives reporting a message: %d (%.1f%%); total messages: %d"
               % (sum(1 for r in records.values() if r.get("messages")),
                  pct(sum(1 for r in records.values() if r.get("messages")), total),
                  len(messages)))
    THEMES = [
        ("love is what matters", r"\blove\b"),
        ("it is not your time / must return", r"not your time|must (go|return)|have to go back"),
        ("purpose / unfinished task", r"purpose|mission|work to do|unfinished|task"),
        ("family / children need you", r"child|children|family|son|daughter|mother"),
        ("do not fear death", r"fear|afraid|nothing to fear"),
        ("everything is connected / oneness", r"connect|oneness|unity|all is one"),
        ("forgiveness", r"forgiv"),
        ("knowledge / understanding given", r"knowledge|understand|answers|truth"),
        ("you are not alone / watched over", r"not alone|watching over|always with"),
        ("choice offered", r"choice|choose|decide"),
    ]
    out.append("")
    out.append("%-38s %8s" % ("theme (keyword-matched paraphrases)", "% of msgs"))
    for label, pattern in THEMES:
        hits = sum(1 for m in messages if re.search(pattern, m))
        out.append("%-38s %7.1f%%" % (label, pct(hits, len(messages))))
    out.append("")
    out.append("Themes are keyword matches over paraphrases, so they are indicative,")
    out.append("not a validated coding - unlike the element labels, these were not")
    out.append("checked against blind annotation.")

    # ---- Q. outliers -------------------------------------------------------
    out += section("Q131-Q132. NARRATIVES THAT FIT NO COMMON PATTERN")
    empty = [k for k, r in records.items()
             if not r.get("sequence") and not r.get("beings") and not r.get("settings")]
    out.append("no sequence, no beings, no setting: %d (%.1f%%)"
               % (len(empty), pct(len(empty), total)))
    common = Counter()
    for sequence in sequences:
        for a, b in zip(sequence, sequence[1:]):
            common[(a, b)] += 1
    rare_score = []
    for key, record in records.items():
        sequence = record.get("sequence") or []
        if len(sequence) < 3:
            continue
        score = sum(common[(a, b)] for a, b in zip(sequence, sequence[1:]))
        rare_score.append((score / max(1, len(sequence) - 1), key, len(sequence)))
    rare_score.sort()
    out.append("")
    out.append("most unusual event orderings (lowest mean transition frequency)")
    for score, key, length in rare_score[:8]:
        out.append("   %-46s %d events, score %.1f" % (key, length, score))

    text = "\n".join(out)
    with open(os.path.join(HERE, "tier3.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
