#!/usr/bin/env python3
"""Turn the three extracted archives into an analysis-ready dataset.

This is the step between scraping and analysis. It does four things the raw
Markdown cannot:

1. HARVEST metadata the pages don't carry (country, age, classification) from
   the search API, working around its 980-record query ceiling.
2. PARSE each corpus into one record per account with typed fields.
3. NORMALIZE questionnaire answers, which arrive as a coded value welded to a
   free-text elaboration ("Yes See main narrative."). Splitting these is the
   single most important correctness step: without it every "Yes" that carries
   elaboration is miscounted, and every downstream percentage is wrong.
4. SEPARATE prompted from spontaneous mentions. An element the questionnaire
   asked about and an element the writer raised unbidden are different kinds of
   evidence, so they are counted in different fields and never merged.

Outputs (analysis/data/):
    nderf.jsonl, adcrf.jsonl, oberf.jsonl   one JSON record per account
    codebook.json                            fields, answer codes, element lexicon
    coverage.txt                             what we have, what we are missing

Usage:
    python3 analysis/prepare.py                  # full run
    python3 analysis/prepare.py --skip-api       # parse only, no network
    python3 analysis/prepare.py --limit 200      # quick smoke test
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from ndescrape.http import Cache, Fetcher, RateLimiter  # noqa: E402
from ndescrape.runner import POOLS  # noqa: E402

OUT_DIR = os.path.join(HERE, "data")
CORPUS_DIR = os.path.join(ROOT, "output")


# ---------------------------------------------------------------------------
# 1. Answer normalization
# ---------------------------------------------------------------------------

# The questionnaire's closed-response vocabulary. Order matters: longer, more
# specific options must be tested before their prefixes, or "Yes I was aware"
# would match the bare "Yes" and lose the distinction from "Yes, but uncertain".
ANSWER_CODES = [
    ("uncertain", r"uncertain"),
    ("yes", r"yes"),
    ("no", r"no"),
    ("not_applicable", r"n/?a\b|not applicable"),
    ("male", r"male"),
    ("female", r"female"),
    ("more_conscious", r"more consciousness and alertness than normal"),
    ("normal_consciousness", r"normal consciousness and alertness"),
    ("less_conscious", r"less consciousness and alertness than normal"),
]
_CODE_RE = re.compile(
    r"^\s*(%s)\b[\s.,;:!-]*" % "|".join("(?:%s)" % pat for _, pat in ANSWER_CODES),
    re.I,
)
_CODE_LOOKUP = [(code, re.compile(r"^(?:%s)$" % pat, re.I)) for code, pat in ANSWER_CODES]


def normalize_answer(text):
    """Split a questionnaire answer into (code, elaboration, raw).

    Answers look like "Yes", "No", "Uncertain I don't remember.", or
    "Yes See main narrative." - a closed-response token followed by optional
    free text. Treating the whole string as the response, which is the obvious
    approach, silently buckets every elaborated answer as its own unique value
    and collapses the real distribution.
    """
    raw = (text or "").strip()
    if not raw:
        return None, "", ""
    match = _CODE_RE.match(raw)
    if not match:
        return None, raw, raw
    token = match.group(1).strip()
    code = None
    for name, pattern in _CODE_LOOKUP:
        if pattern.match(token):
            code = name
            break
    if code is None:
        code = re.sub(r"\W+", "_", token.lower()).strip("_") or None
    return code, raw[match.end():].strip(), raw


# ---------------------------------------------------------------------------
# 2. Element lexicon - for SPONTANEOUS detection in narrative text
# ---------------------------------------------------------------------------

# Deliberately conservative: high-precision phrases rather than broad terms, so
# a spontaneous "hit" means the writer really described the element rather than
# happening to use a common word. Recall is sacrificed on purpose - an inflated
# spontaneous count would defeat the point of separating it from prompted.
ELEMENT_LEXICON = OrderedDict([
    ("out_of_body", [
        r"out of (?:my |the )?body", r"outside (?:of )?my body", r"left my body",
        r"above my body", r"looking down (?:at|on) (?:my|myself)",
        r"floating (?:above|over) (?:my|the)", r"separated from my body",
    ]),
    ("tunnel", [r"\btunnel\b", r"through a (?:dark )?(?:passage|corridor|shaft)"]),
    ("light", [
        r"\bbright light\b", r"\bbrilliant light\b", r"\bwhite light\b",
        r"\bthe light\b", r"\bbeing of light\b", r"light at the end",
    ]),
    ("life_review", [
        r"life review", r"my (?:whole|entire) life (?:flashed|passed)",
        r"scenes from my (?:past|life)", r"reliv(?:ed|ing) (?:my|every)",
    ]),
    ("deceased_beings", [
        r"(?:my |our )?(?:deceased|dead|late) (?:mother|father|grandmother|grandfather"
        r"|brother|sister|son|daughter|husband|wife|friend|aunt|uncle|cousin)",
        r"(?:who|whom) had (?:died|passed away)", r"already (?:died|passed)",
    ]),
    ("border", [
        r"point of no return", r"\ba border\b", r"\bboundary\b",
        r"if i cross(?:ed)?", r"could not go (?:any )?(?:further|farther)",
    ]),
    ("ineffable", [
        r"(?:can|could)(?:not|n't) (?:be )?(?:describe|explain|put into words)",
        r"no words (?:to|can|could)", r"beyond (?:words|description|language)",
        r"words (?:cannot|can't|fail)", r"indescribable",
    ]),
    ("realer_than_real", [
        r"realer than", r"more real than (?:this|real|life|anything)",
        r"hyper[- ]?real",
    ]),
    ("altered_time", [
        r"time (?:had )?(?:no meaning|stood still|did ?n[o']?t exist|ceased)",
        r"no (?:sense|concept) of time", r"timeless", r"time (?:slowed|sped up)",
    ]),
    ("total_understanding", [
        r"(?:knew|understood) everything", r"all(?:-| )knowing",
        r"understood (?:the|all) (?:answers|meaning)", r"universal knowledge",
    ]),
    ("telepathy", [
        r"without (?:speaking|words|talking)", r"telepath", r"mind to mind",
        r"communicated? (?:by|through) thought",
    ]),
    ("unconditional_love", [
        r"unconditional love", r"overwhelming love", r"pure love",
        r"love (?:that|which) (?:i|words)",
    ]),
    ("peace", [r"complete peace", r"total peace", r"peace(?:ful)? beyond", r"such peace"]),
    ("fear_terror", [r"\bterrified\b", r"\bterror\b", r"\bhorrif", r"\bfrightening\b"]),
    ("darkness_void", [r"\bthe void\b", r"total darkness", r"complete darkness", r"\bblackness\b"]),
    ("music_sound", [r"\bmusic\b", r"\bsinging\b", r"\bchoir\b", r"beautiful sound"]),
    ("religious_figure", [
        r"\bjesus\b", r"\bchrist\b", r"\bgod\b", r"\ballah\b", r"\bbuddha\b",
        r"\bkrishna\b", r"\bvirgin mary\b", r"\bangel", r"\bmuhammad\b",
    ]),
    ("garden_landscape", [
        r"\bmeadow\b", r"\bgarden\b", r"\bfield of (?:flowers|grass)\b",
        r"\bgreen(?:est)? (?:grass|fields)\b",
    ]),
    ("reluctant_return", [
        r"did ?n[o']?t want to (?:come|go) back", r"did ?n[o']?t want to return",
        r"begged to stay", r"forced to (?:return|come back)",
    ]),
    ("chose_return", [
        r"chose to (?:return|come back)", r"my choice to (?:return|come back)",
        r"decided to (?:return|come back)", r"asked (?:me )?if i wanted to",
    ]),
    ("no_fear_of_death", [
        r"no(?:t| longer)? (?:afraid|fear) of (?:death|dying)",
        r"lost my fear of (?:death|dying)", r"do ?n[o']?t fear death",
    ]),
])

COMPILED_LEXICON = OrderedDict(
    (name, [re.compile(p, re.I) for p in pats]) for name, pats in ELEMENT_LEXICON.items()
)


def spontaneous_elements(narrative):
    """Elements the writer raised unprompted, in their own narrative.

    Runs ONLY against the free-text narrative, never the questionnaire answers,
    so a hit here means the person volunteered it rather than responding to a
    question that named it.
    """
    found = {}
    if not narrative:
        return found
    for name, patterns in COMPILED_LEXICON.items():
        hits = sum(len(p.findall(narrative)) for p in patterns)
        if hits:
            found[name] = hits
    return found


# ---------------------------------------------------------------------------
# 3. Corpus parsing
# ---------------------------------------------------------------------------

_STORY_SPLIT = re.compile(r"\n---\n\n")
_HEADING = re.compile(r"^## (?:\d+\.\s*)?(.+)$", re.M)
_META = re.compile(r"^- \*\*([^:*]+):\*\* (.+)$", re.M)
_SECTION = re.compile(r"^### (.+?)\n\n(.*?)(?=\n### |\Z)", re.M | re.S)


def parse_corpus(path, limit=None):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    records = []
    for block in _STORY_SPLIT.split(text):
        heading = _HEADING.search(block)
        if not heading:
            continue  # the file header, not an account

        metadata = {k.strip(): v.strip() for k, v in _META.findall(block)}
        url = metadata.pop("Source", "")

        sections = OrderedDict()
        for label, body in _SECTION.findall(block):
            sections[label.strip()] = body.strip()

        # Narrative = everything between the metadata list and the first ###.
        body_start = block.find("\n\n", heading.end())
        first_section = block.find("\n### ")
        narrative = block[body_start:first_section if first_section > 0 else len(block)]
        narrative = re.sub(r"^- \*\*.*$", "", narrative, flags=re.M).strip()

        records.append({
            "title": heading.group(1).strip(),
            "url": url,
            "metadata": metadata,
            "narrative": narrative,
            "sections": sections,
        })
        if limit and len(records) >= limit:
            break
    return records


# ---------------------------------------------------------------------------
# 4. API metadata harvest
# ---------------------------------------------------------------------------

API = "https://search.nderf.org/api/get?e=%s"
COUNTRIES_JS = "https://search.nderf.org/static/scripts/countries.js"
PAGE_SIZE = 20
MAX_PAGES = 49          # server 500s from page 49 onward
REACHABLE = PAGE_SIZE * MAX_PAGES   # 980 records per query, per sort order

# Each sort order is a different 980-record window onto the same result set, and
# measurement shows the windows barely overlap (~14%). Six of them therefore
# reach roughly five times as far as one, which is what makes buckets larger
# than the cap recoverable at all.
SORT_ORDERS = [
    ("POSTDATE", False), ("POSTDATE", True),
    ("ENTRYNUM", False), ("ENTRYNUM", True),
    ("EXPDATE", False), ("EXPDATE", True),
]

# Facets used to split oversized buckets, most discriminating first. These are
# NOT covering partitions - records with a missing value fall through every
# child - so the parent is always harvested too and results are unioned.
FACETS = [
    ("COUNTRY", []),   # filled at runtime from countries.js - see load_countries()
    ("GENDER", ["M", "F"]),
    ("age", ["Baby", "College Age", "Adult", "Older Adult"]),
    ("CLASSIFICATION", ["NDE", "Probable NDE", "Possible NDE", "STE", "FDE", "SDE", "OBE"]),
]


def api_query(fetch, params, page, sort="POSTDATE", ascending=False):
    parts = ["sort=%s" % sort, "lang=en"]
    for key, value in params.items():
        parts.append("%s=%s" % (key, value))
    if ascending:
        parts.append("ascending=1")
    parts.append("page=%d" % page)
    query = "&".join(parts)
    encoded = base64.b64encode(query.encode("utf-8")).decode("ascii")
    return json.loads(fetch(API % encoded))


def harvest_bucket(fetch, params, docs, log, depth=0):
    """Collect every record matching `params`, splitting if it exceeds the cap."""
    try:
        head = api_query(fetch, params, 0)
    except Exception as exc:  # noqa: BLE001
        log("    %sbucket failed %s (%s)" % ("  " * depth, params, exc))
        return
    count = head.get("resultCount", 0)
    if not count:
        return

    label = ", ".join("%s=%s" % kv for kv in params.items()) or "(all)"

    if count <= REACHABLE:
        added = 0
        for page in range(min(MAX_PAGES, -(-count // PAGE_SIZE))):
            try:
                payload = api_query(fetch, params, page)
            except Exception:  # noqa: BLE001
                break
            results = payload.get("results") or []
            if not results:
                break
            for doc in results:
                key = doc.get("_id") or doc.get("storyid")
                if key and key not in docs:
                    docs[key] = doc
                    added += 1
        log("    %s%-52s rc=%-5d +%d" % ("  " * depth, label[:52], count, added))
        return

    # Too big to page through in one order. Sweep every sort window, then split.
    before = len(docs)
    for sort, ascending in SORT_ORDERS:
        for page in range(MAX_PAGES):
            try:
                payload = api_query(fetch, params, page, sort, ascending)
            except Exception:  # noqa: BLE001
                break
            results = payload.get("results") or []
            if not results:
                break
            for doc in results:
                key = doc.get("_id") or doc.get("storyid")
                if key and key not in docs:
                    docs[key] = doc
    log("    %s%-52s rc=%-5d +%d (split)" % ("  " * depth, label[:52], count, len(docs) - before))

    for name, values in FACETS:
        if name in params:
            continue
        for value in values:
            child = dict(params)
            child[name] = value
            harvest_bucket(fetch, child, docs, log, depth + 1)
        return  # one facet level per recursion step


def load_countries(fetch, log):
    """The site ships its own country vocabulary; use it rather than guessing.

    A hardcoded shortlist leaves every other country's records reachable only
    through the capped root bucket, which is where most of the previous run's
    missing records were hiding.
    """
    try:
        body = fetch(COUNTRIES_JS)
        inner = re.search(r"\[(.*?)\]", body, re.S)
        names = re.findall(r"'([^']+)'", inner.group(1)) if inner else []
        if names:
            log("  country vocabulary: %d entries" % len(names))
            return names
    except Exception as exc:  # noqa: BLE001
        log("  ! countries.js unavailable (%s)" % exc)
    return ["United States", "United Kingdom", "Canada", "Australia", "India"]


def harvest_api(fetch, log):
    for index, (name, values) in enumerate(FACETS):
        if name == "COUNTRY" and not values:
            FACETS[index] = (name, load_countries(fetch, log))
    docs = {}
    harvest_bucket(fetch, {}, docs, log)
    return docs


# ---------------------------------------------------------------------------
# 5. Matching API records to scraped accounts
# ---------------------------------------------------------------------------

def slug_key(url):
    slug = re.sub(r"\.html?$", "", (url or "").rsplit("/", 1)[-1].lower())
    return re.sub(r"^1(?=[a-z])", "", slug)


def name_key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def entry_numbers(doc):
    nums = set()
    if doc.get("ENTRYNUM"):
        nums |= set(re.findall(r"\d+", str(doc["ENTRYNUM"])))
    for item in (doc.get("experiences") or []):
        if item.get("ENTRYNUM") is not None:
            nums.add(str(item["ENTRYNUM"]))
    return nums


def build_index(docs):
    """Index API records under every key we might later match on."""
    by_slug, by_name, by_entry = {}, {}, {}
    for doc in docs.values():
        url = doc.get("URL") or ""
        if "/Experiences/" in url:
            by_slug.setdefault(slug_key(url), doc)
        name = name_key(doc.get("POSTNAME"))
        if name:
            by_name.setdefault(name, []).append(doc)
        for number in entry_numbers(doc):
            by_entry.setdefault(number, doc)
    return by_slug, by_name, by_entry


def match_record(record, by_slug, by_name, by_entry):
    """Find the API record for a scraped account. Returns (doc, how)."""
    key = slug_key(record["url"])
    if key in by_slug:
        return by_slug[key], "slug"

    # Newer accounts carry the entry number in the filename and title
    # ("ashley_m_nde_33394.htm" / "Ashley M NDE 33394"). Older ones do not, and
    # the number there is NOT an entry number - so this is a fallback, never the
    # primary key.
    for number in re.findall(r"_(\d{2,6})\.html?$", record["url"]):
        if number in by_entry:
            return by_entry[number], "entrynum"

    # Titles read like "Agnes G NDE 13435" - the leading words are the display
    # name the API stores as POSTNAME.
    title = re.sub(r"\s+\d[\d/,\s]*$", "", record["title"]).strip()
    title = re.sub(
        r"\s+(?:NDE|NDEs|OBE|OBEs|ADC|ADCs|STE|FDE|SDE|DBV|NELE)[- ]?[Ll]ike?\s*$",
        "", title,
    ).strip()
    candidates = by_name.get(name_key(title)) or []
    if len(candidates) == 1:
        return candidates[0], "postname"
    if len(candidates) > 1:
        # Disambiguate on the experience date the questionnaire recorded.
        stated = record["sections"].get("Date NDE Occurred") or ""
        years = set(re.findall(r"(19\d{2}|20\d{2})", stated))
        if years:
            for doc in candidates:
                doc_years = set(re.findall(r"(19\d{2}|20\d{2})", json.dumps(doc.get("EXPDATE") or [])))
                if years & doc_years:
                    return doc, "postname+date"
    return None, "unmatched"


ENRICH_FIELDS = [
    ("country", "COUNTRY_AI"), ("age_bucket", "AGE"), ("gender_api", "GENDER"),
    ("classification", "CLASSIFICATION"), ("exceptional", "EXCEPTIONAL"),
    ("condition", "Condition"), ("editorial", "Editorial"),
    ("entrynum", "ENTRYNUM"), ("api_id", "_id"),
]


# ---------------------------------------------------------------------------
# 6. Record assembly
# ---------------------------------------------------------------------------

def build_record(site, raw, doc, how):
    answers = OrderedDict()
    for label, body in raw["sections"].items():
        code, elaboration, original = normalize_answer(body)
        answers[label] = {
            "code": code,
            "text": elaboration,
            "raw": original,
            "has_elaboration": bool(elaboration),
        }

    record = {
        "site": site,
        "title": raw["title"],
        "url": raw["url"],
        "narrative": raw["narrative"],
        "narrative_words": len(raw["narrative"].split()),
        "answer_words": sum(len(a["raw"].split()) for a in answers.values()),
        "n_questions": len(answers),
        "answers": answers,
        # Kept in separate keys on purpose - prompted and spontaneous evidence
        # are never summed.
        "spontaneous": spontaneous_elements(raw["narrative"]),
        "page_metadata": raw["metadata"],
        "match": how,
    }
    if doc:
        for field, key in ENRICH_FIELDS:
            value = doc.get(key)
            if value not in (None, "", []):
                record[field] = value
        greyson = (doc.get("metadata") or {}).get("greyson")
        if greyson is not None:
            record["greyson"] = greyson
        exp = doc.get("EXPDATE") or []
        post = doc.get("POSTDATE") or []
        if exp:
            record["experience_date"] = exp[0]
        if post:
            record["submit_date"] = post[0]
    return record


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-api", action="store_true", help="parse only, no network")
    parser.add_argument("--limit", type=int, default=None, help="accounts per site")
    parser.add_argument("--out", default=OUT_DIR)
    parser.add_argument("--delay", type=float, default=0.35)
    args = parser.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    log = lambda message: print(message, file=sys.stderr)

    fetcher = Fetcher(
        cache=Cache(os.path.join(ROOT, ".cache")),
        limiter=RateLimiter(args.delay, POOLS),
        log=log,
    )

    docs = {}
    api_path = os.path.join(args.out, "api_records.json")
    if args.skip_api:
        if os.path.exists(api_path):
            docs = json.load(open(api_path, encoding="utf-8"))
            log("[api] reusing %d cached records" % len(docs))
    else:
        log("[api] harvesting search index (this works around the 980/query cap)")
        docs = harvest_api(fetcher.get, log)
        with open(api_path, "w", encoding="utf-8") as handle:
            json.dump(docs, handle)
        log("[api] %d unique records" % len(docs))

    by_slug, by_name, by_entry = build_index(docs)
    coverage = []

    for site in ("nderf", "adcrf", "oberf"):
        source = os.path.join(CORPUS_DIR, "%s.md" % site)
        if not os.path.exists(source):
            log("[%s] missing %s - skipping" % (site, source))
            continue

        raws = parse_corpus(source, args.limit)
        how_counts = Counter()
        field_counts = Counter()
        destination = os.path.join(args.out, "%s.jsonl" % site)

        with open(destination, "w", encoding="utf-8") as handle:
            for raw in raws:
                if site == "nderf":
                    doc, how = match_record(raw, by_slug, by_name, by_entry)
                else:
                    doc, how = None, "n/a"
                how_counts[how] += 1
                record = build_record(site, raw, doc, how)
                for field, _ in ENRICH_FIELDS:
                    if field in record:
                        field_counts[field] += 1
                for field in ("greyson", "experience_date", "submit_date"):
                    if field in record:
                        field_counts[field] += 1
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        total = len(raws)
        coverage.append((site, total, how_counts, field_counts))
        log("[%s] %d accounts -> %s" % (site, total, destination))

    # Codebook: what a downstream analysis needs to interpret the fields.
    codebook = {
        "answer_codes": [code for code, _ in ANSWER_CODES],
        "element_lexicon": {k: v for k, v in ELEMENT_LEXICON.items()},
        "enrich_fields": [field for field, _ in ENRICH_FIELDS],
        "notes": {
            "prompted_vs_spontaneous":
                "answers[*].code is a PROMPTED response - the questionnaire named "
                "the element. spontaneous[*] counts mentions the writer raised "
                "unbidden in their own narrative. Never sum the two; report them "
                "side by side. The gap between them is itself a finding.",
            "answer_code_null":
                "code=null means the answer did not begin with a closed-response "
                "token - it is free text. Those belong in a text analysis, not a "
                "frequency table.",
            "denominator":
                "Percentages must state their base: of all accounts, or of those "
                "who answered that question. n_questions varies by questionnaire "
                "version and the two bases differ substantially.",
        },
    }
    with open(os.path.join(args.out, "codebook.json"), "w", encoding="utf-8") as handle:
        json.dump(codebook, handle, indent=2, ensure_ascii=False)

    report = [
        "PREPARATION COVERAGE",
        "=" * 64,
        "API records harvested: %d" % len(docs),
        "",
    ]
    for site, total, how_counts, field_counts in coverage:
        report.append("%s  (%d accounts)" % (site.upper(), total))
        if site == "nderf":
            report.append("  match method:")
            for how, n in how_counts.most_common():
                report.append("    %-16s %5d  %5.1f%%" % (how, n, 100.0 * n / max(1, total)))
        report.append("  enriched field coverage:")
        for field, n in field_counts.most_common():
            report.append("    %-18s %5d  %5.1f%%" % (field, n, 100.0 * n / max(1, total)))
        report.append("")
    text = "\n".join(report)
    with open(os.path.join(args.out, "coverage.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
