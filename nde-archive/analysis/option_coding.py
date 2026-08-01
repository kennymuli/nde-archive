"""Explicit response coding for the questionnaire's closed options.

Why this file exists: the instrument is NOT uniformly yes/no. Some items offer
descriptive alternatives instead, and for those the word "yes" never appears in
any valid answer. A generic "count the yeses" rule therefore reports ~0% for
items that a majority actually affirmed - measured on this corpus, it put
altered_time at 0.0% when 3,354 respondents chose "Everything seemed to be
happening at once; or time stopped or lost all meaning".

So every item's option vocabulary is coded by hand below. Three distinctions
matter and are easy to get wrong:

  * "Neither" is a NEGATIVE response - the respondent was offered alternatives
    and rejected all of them.
  * "No response" / "No comment" are MISSING, not negative. They start with the
    letters "no", so any prefix match must test them first or they silently
    become negatives and deflate every rate.
  * Some items have a middle option (out_of_body's "I lost awareness of my body")
    that is neither a clear yes nor a clear no. Those are coded PARTIAL and
    reported separately rather than being forced to one side.
"""

import re

MISSING = [
    "no response", "no responses", "no comment", "n0 comment", "no answer",
    "not applicable", "n/a", "na", "none given",
]
UNCERTAIN = ["uncertain", "unsure", "i don't remember", "i do not remember", "don't know"]
NEGATIVE = ["no", "neither", "none", "nothing"]

# element -> {"aff": [...], "partial": [...]}  (negatives come from NEGATIVE)
CODING = {
    "out_of_body": {
        "aff": ["yes", "i clearly left my body and existed outside it"],
        "partial": ["i lost awareness of my body"],
    },
    "tunnel": {"aff": ["yes"], "partial": []},
    "light": {
        "aff": ["yes", "a light clearly of mystical or other-worldly origin",
                "an unusually bright light", "light clearly of mystical or other-worldly origin"],
        "partial": [],
    },
    "life_review": {
        "aff": ["my past flashed before me, out of my control",
                "past flashed before me, out of my control",
                "i remembered many past events", "remembered many past events"],
        "partial": [],
    },
    "deceased_beings": {"aff": ["yes"], "partial": []},
    "border": {
        "aff": ["i came to a barrier that i was not permitted to cross; or was sent back against my will",
                "a barrier i was not permitted to cross; or 'sent back' to life involuntarily",
                "i came to a definite conscious decision to return to life",
                "a conscious decision to 'return' to life"],
        "partial": [],
    },
    "ineffable": {"aff": ["yes"], "partial": []},
    "altered_time": {
        "aff": ["everything seemed to be happening at once; or time stopped or lost all meaning",
                "everything seemed to be happening all at once",
                "time seemed to go faster or slower than usual",
                "time seemed to go faster than usual",
                "time seemed to go slower than usual"],
        "partial": [],
    },
    "total_understanding": {
        "aff": ["everything about the universe", "everything about myself or others"],
        "partial": [],
    },
    "unearthly_world": {
        "aff": ["a clearly mystical or unearthly realm", "clearly mystical or unearthly realm"],
        "partial": ["some unfamiliar and strange place", "unfamiliar, strange place"],
    },
    "future_scenes": {
        "aff": ["scenes from the world's future", "scenes from my personal future",
                "from personal future", "from the world's future"],
        "partial": [],
    },
    "psychic_after": {"aff": ["yes"], "partial": []},
    "values_changed": {"aff": ["yes"], "partial": []},
}

_PUNCT = re.compile(r"[^a-z0-9' ;,]+")
_WS = re.compile(r"\s+")


def normalize(text):
    text = (text or "").strip().lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _match(normalized, options):
    """Longest option that the answer starts with, so elaboration is tolerated."""
    best = None
    for option in options:
        candidate = normalize(option)
        if normalized == candidate or normalized.startswith(candidate + " "):
            if best is None or len(candidate) > len(best):
                best = candidate
    return best


def classify(element, raw):
    """Return one of: affirmative, partial, negative, uncertain, missing, other."""
    normalized = normalize(raw)
    if not normalized:
        return "missing"

    # Missing first: "no response" would otherwise be captured by "no".
    if _match(normalized, MISSING):
        return "missing"

    coding = CODING.get(element) or {"aff": ["yes"], "partial": []}
    affirmative = _match(normalized, coding["aff"])
    partial = _match(normalized, coding.get("partial") or [])
    negative = _match(normalized, NEGATIVE)
    uncertain = _match(normalized, UNCERTAIN)

    # Longest match wins, so a descriptive affirmative beats a bare "no" prefix.
    candidates = [
        (len(affirmative or ""), "affirmative"),
        (len(partial or ""), "partial"),
        (len(negative or ""), "negative"),
        (len(uncertain or ""), "uncertain"),
    ]
    length, label = max(candidates)
    return label if length else "other"


def rate(records, labels, element):
    """Affirmative share among valid responses, plus the full breakdown.

    Denominator excludes missing and unparseable answers, and 'partial' is kept
    out of the headline numerator - it is reported separately so a reader can
    decide whether to include it.
    """
    counts = {k: 0 for k in
              ("affirmative", "partial", "negative", "uncertain", "missing", "other")}
    for record in records:
        answer = None
        for label in labels:
            if label in record["answers"]:
                answer = record["answers"][label]
                break
        if answer is None:
            continue
        counts[classify(element, answer["raw"])] += 1

    valid = counts["affirmative"] + counts["partial"] + counts["negative"] + counts["uncertain"]
    return counts, valid
