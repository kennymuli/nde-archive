#!/usr/bin/env python3
"""Score the spontaneous-element regexes against blind human-style labels.

Reads:
    analysis/validation/labels_primary.json     [{id, present, uncertain}, ...]
    analysis/validation/labels_replicate.json   same, for a subset of batches
    analysis/validation/regex_output.json       {id: [elements the regexes found]}

Reports per element:
    precision - of the narratives the regexes flagged, how many really had it
    recall    - of the narratives that really had it, how many the regexes caught
    F1

Recall is the number that matters here. The regexes were deliberately tuned for
precision, so the open question was never "are the hits real" but "how much is
being missed" - because a low recall would make any prompted-vs-spontaneous gap
an artifact of the patterns rather than a property of the corpus.

Agreement between the two independent labellers bounds how much of the
disagreement with the regexes is labelling noise rather than regex error: the
regexes cannot meaningfully be held to a standard tighter than the labellers
manage with each other.
"""

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
VAL = os.path.join(HERE, "validation")

ELEMENTS = [
    "out_of_body", "tunnel", "light", "life_review", "deceased_beings", "border",
    "ineffable", "realer_than_real", "altered_time", "total_understanding",
    "telepathy", "unconditional_love", "peace", "fear_terror", "darkness_void",
    "music_sound", "religious_figure", "garden_landscape", "reluctant_return",
    "chose_return", "no_fear_of_death",
]


def load_labels(path):
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    out = {}
    for item in raw:
        out[item["id"]] = {
            "present": set(item.get("present") or []),
            "uncertain": set(item.get("uncertain") or []),
        }
    return out


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision and recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    return precision, recall, f1


def fmt(value):
    return "  -  " if value is None else "%5.2f" % value


def score(labels, regex, lenient):
    """lenient=True credits the regexes for 'uncertain' labels either way."""
    stats = defaultdict(lambda: Counter())
    for key, truth in labels.items():
        found = set(regex.get(key, []))
        positive = set(truth["present"])
        ambiguous = set(truth["uncertain"])
        for element in ELEMENTS:
            in_truth = element in positive
            in_regex = element in found
            if element in ambiguous and lenient:
                continue  # neither credited nor penalised
            if in_truth and in_regex:
                stats[element]["tp"] += 1
            elif in_regex and not in_truth:
                stats[element]["fp"] += 1
            elif in_truth and not in_regex:
                stats[element]["fn"] += 1
            else:
                stats[element]["tn"] += 1
    return stats


def agreement(a, b):
    """Cohen's kappa over element-presence decisions on shared narratives."""
    shared = set(a) & set(b)
    if not shared:
        return None, 0, None
    both = neither = only_a = only_b = 0
    for key in shared:
        for element in ELEMENTS:
            x = element in a[key]["present"]
            y = element in b[key]["present"]
            if x and y:
                both += 1
            elif x:
                only_a += 1
            elif y:
                only_b += 1
            else:
                neither += 1
    total = both + neither + only_a + only_b
    observed = (both + neither) / total
    pa = (both + only_a) / total
    pb = (both + only_b) / total
    expected = pa * pb + (1 - pa) * (1 - pb)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else None
    return kappa, len(shared), observed


def main():
    primary = load_labels(os.path.join(VAL, "labels_primary.json"))
    replicate = load_labels(os.path.join(VAL, "labels_replicate.json"))
    regex = json.load(open(os.path.join(VAL, "regex_output.json"), encoding="utf-8"))

    if not primary:
        print("no primary labels found - run the labelling workflow first", file=sys.stderr)
        return 1

    lines = []
    lines.append("LEXICON VALIDATION")
    lines.append("=" * 74)
    lines.append("narratives labelled: %d" % len(primary))

    kappa, shared, observed = agreement(primary, replicate)
    if kappa is not None:
        lines.append(
            "inter-labeller agreement on %d shared narratives: kappa=%.2f (raw %.1f%%)"
            % (shared, kappa, 100 * observed)
        )
        lines.append(
            "  -> regex recall below roughly %.0f%% is a regex problem;"
            " above it, labelling noise dominates" % (100 * observed)
        )
    else:
        lines.append("no replicate labels - inter-labeller agreement unmeasured")
    lines.append("")

    stats = score(primary, regex, lenient=True)
    lines.append("%-20s %5s %5s %5s  %5s %5s %5s" % (
        "element", "TP", "FP", "FN", "prec", "rec", "F1"))
    lines.append("-" * 74)

    weak = []
    for element in ELEMENTS:
        row = stats[element]
        precision, recall, f1 = prf(row["tp"], row["fp"], row["fn"])
        lines.append("%-20s %5d %5d %5d  %s %s %s" % (
            element, row["tp"], row["fp"], row["fn"], fmt(precision), fmt(recall), fmt(f1)))
        if recall is not None and recall < 0.60 and (row["tp"] + row["fn"]) >= 3:
            weak.append((element, recall, row["fn"]))

    total = Counter()
    for row in stats.values():
        total.update(row)
    precision, recall, f1 = prf(total["tp"], total["fp"], total["fn"])
    lines.append("-" * 74)
    lines.append("%-20s %5d %5d %5d  %s %s %s" % (
        "OVERALL (micro)", total["tp"], total["fp"], total["fn"],
        fmt(precision), fmt(recall), fmt(f1)))

    lines.append("")
    if weak:
        lines.append("LOW RECALL - these under-count and need patterns added:")
        for element, value, missed in sorted(weak, key=lambda x: x[1]):
            lines.append("  %-20s recall %.2f  (%d missed)" % (element, value, missed))
    else:
        lines.append("no element falls below 0.60 recall on this sample")

    text = "\n".join(lines)
    with open(os.path.join(VAL, "score.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
