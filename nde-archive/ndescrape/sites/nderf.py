"""nderf.org - Near Death Experience Research Foundation.

Discovery deliberately uses the static Archives spine rather than the search API.
The API advertises 292 pages but returns HTTP 500 for any page >= 49, capping a
single query at 980 of its 5,826 records, and its filter fields (age, GENDER,
CLASSIFICATION) are not covering partitions - each silently drops records - so no
combination of queries can be shown to reach everything. The 54 archive pages
yield 5,811 story URLs, within 0.3% of the API's own total, from static HTML with
no such traps. The API is still consulted, but only to enrich metadata and to
backfill the handful of stories the archives miss.
"""

import base64
import json
import re
from urllib.parse import unquote, urljoin, urlparse

from .. import htmltext
from ..record import Story

SITE_KEY = "nderf"
SITE_TITLE = "NDERF - Near Death Experience Research Foundation"
SITE_URL = "https://www.nderf.org/"
BASE = "https://www.nderf.org"
API = "https://search.nderf.org/api/get?e=%s"

ARCHIVE_LIST = "https://www.nderf.org/Archives/archivelist.htm"
ARCHIVE_RE = re.compile(
    r'href="(https://www\.nderf\.org/Archives/[^"]+\.html?)"', re.I
)
EXPERIENCE_RE = re.compile(
    r'href="(https?://www\.nderf\.org/Experiences/[^"]+?\.html?)"', re.I
)
# Index pages that live under /Archives/ but list stories rather than being one.
ARCHIVE_SKIP = re.compile(r"/(archivelist|NDERF_NDEs|exceptional)\.html?$", re.I)

LANGUAGE_MIRROR_RE = re.compile(
    r"^/(French|Italian|Serbian|Arabic|Polish|Thai|Turkish|Hindi|Urdu|Greek"
    r"|Spanish|Portuguese|Romanian|Chinese|ChineseSimple|Korean|Indonesian|Hebrew"
    r"|Macedonian|Basque|German|Swedish|Persian|Hungarian|Dutch|Croatian|Slovak"
    r"|Ukranian|Vietnamese|Russian|Japanese|Danish|Finnish|Czech|Bulgarian"
    r"|Lithuanian|Afrikaans)/",
    re.I,
)


def api_url(query):
    return API % base64.b64encode(query.encode("utf-8")).decode("ascii")


def fetch_index(fetch, log, max_pages=49):
    """Pull what the search API will give us, for metadata enrichment.

    Stops at the server's hard page-48 ceiling rather than trusting totalPages.
    """
    docs = {}
    for sort_order in ("sort=POSTDATE&lang=en", "sort=POSTDATE&lang=en&ascending=1"):
        for page in range(max_pages):
            try:
                raw = fetch(api_url("%s&page=%d" % (sort_order, page)))
                payload = json.loads(raw)
            except Exception as exc:  # noqa: BLE001 - the API 500s past its cap
                log("  api stopped at page %d (%s)" % (page, exc))
                break
            results = payload.get("results") or []
            if not results:
                break
            for doc in results:
                key = doc.get("_id") or doc.get("storyid")
                if key:
                    docs[key] = doc
        log("  api %-34s cumulative docs=%d" % (sort_order, len(docs)))
    return docs


def _slug(url):
    return unquote(urlparse(url).path.rsplit("/", 1)[-1]).lower()


def _slug_key(url):
    """Collapse .htm/.html variants and the leading '1' some slugs carry.

    The trailing _NNNN must be preserved: it is what distinguishes different
    contributors who share a name (there are seven separate "John B NDE"
    accounts), so stripping it silently merges unrelated stories.
    """
    slug = re.sub(r"\.html?$", "", _slug(url))
    return re.sub(r"^1(?=[a-z])", "", slug)


def discover(fetch, log):
    markup = fetch(ARCHIVE_LIST)
    archives = sorted(
        set(u for u in ARCHIVE_RE.findall(markup) if not ARCHIVE_SKIP.search(u))
    )
    log("  archive index -> %d archive pages" % len(archives))

    urls = set()
    for position, archive in enumerate(archives, 1):
        try:
            page = fetch(archive)
        except Exception as exc:  # noqa: BLE001
            log("  ! archive failed %s (%s)" % (archive, exc))
            continue
        found = set(EXPERIENCE_RE.findall(page))
        urls |= found
        if position % 15 == 0 or position == len(archives):
            log("  archives %d/%d  running total=%d" % (position, len(archives), len(urls)))

    keep = []
    for url in urls:
        path = urlparse(url).path
        if LANGUAGE_MIRROR_RE.match(path):
            continue
        keep.append(url.replace("http://", "https://"))

    # Collapse .htm/.html duplicates of the same slug, preferring .html.
    by_key = {}
    for url in keep:
        key = _slug_key(url)
        if key not in by_key or url.endswith(".html"):
            by_key[key] = url
    result = sorted(by_key.values())
    log("  -> %d story URLs" % len(result))
    return result


# -- extraction ------------------------------------------------------------
#
# Two templates. The legacy /Experiences/ pages use numbered span classes; the
# modern search.nderf.org/experience/<N> pages use exp-p/exp-a divs. Every marker
# below is matched with \s* rather than literal newlines, because legacy pages are
# CRLF throughout and literal "\n" markers silently match nothing.

# Three legacy vintages coexist. The newest tags structure with .m105/.m108
# classes; older ones inline the same two colours (#009999 for a question label,
# #0080FF for a section header) and head the page with an <h3> instead. Matching
# the colours as well as the classes covers all three with one pass.
SECTION_MARKER_RE = re.compile(
    r'<span class="m108">(.*?)</span>'
    r'|<span[^>]*style="[^"]*color:\s*\#0080FF[^"]*"[^>]*>(.*?)</span>'
    r"|<h3[^>]*>(.*?)</h3>",
    re.I | re.S,
)
QUESTION_MARKER_RE = re.compile(
    r'<span class="m105">(.*?)</span>'
    r'|<span[^>]*style="[^"]*color:\s*\#009999[^"]*"[^>]*>(.*?)</span>',
    re.I | re.S,
)
# Multi-experience pages qualify the heading with either an entry number
# ("Experience Description 9028:") or a date ("Experience Description 12/6/2002").
DESC_HEADER_RE = re.compile(r"^\s*experience\s+description\b[\s\d/:.\-]*$", re.I)
# <!--HERE--> on the newest template, <!--content--> on the older ones.
LEGACY_START_RE = re.compile(r"<!--\s*(?:HERE|content)\s*-->", re.I)
LEGACY_END_RE = re.compile(r"<!--\s*footer\s*-->", re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

MODERN_START_RE = re.compile(r'<div id="experience-div">', re.I)
MODERN_END_RE = re.compile(r"<!--\s*END CONTENT HERE\s*-->", re.I)
EXP_DIV_RE = re.compile(r'<div class="exp"[^>]*>(.*?)</div>', re.I | re.S)
EXP_QA_RE = re.compile(
    r'<div class="exp-p">(.*?)</div>\s*<div class="exp-a"[^>]*>(.*?)</div>', re.I | re.S
)
EXP_TITLE_RE = re.compile(r'<h1 class="exp-title">(.*?)</h1>', re.I | re.S)
QUICK_FACT_RE = re.compile(
    r'<li><span class="quick-facts-label">(.*?)</span>'
    r'<span class="quick-facts-value">(.*?)</span></li>',
    re.I | re.S,
)
GREYSON_RE = re.compile(r"Greyson Scale:\s*(\d+)", re.I)
VAR_EXP_RE = re.compile(r"var\s+exp\s*=\s*(\{.*?\});\s*\n\s*var\s+expEventName", re.S)

# A promotional block the site injects into some narratives.
AD_RE = re.compile(
    r"(?is)\s*(?:www\.)?TheInnerBuddha\.com.*?(?:Click here[^\n]*|Enlightening Strikes\)?)\s*"
)
REDIRECT_STUB_RE = re.compile(
    r"Please follow\s*<a href=\"([^\"]+)\">this link</a>", re.I
)


def _clean(fragment):
    text = htmltext.detag(fragment)
    text = AD_RE.sub("\n", text)
    # Some narratives open with a leftover date crumb such as ") 10/24/2004".
    text = re.sub(r"^\s*\)\s*\d{1,2}/\d{1,2}/\d{2,4}\s*", "", text)
    return htmltext.tidy(text)


def _title(markup, url, fallback_re=None):
    if fallback_re:
        match = fallback_re.search(markup)
        if match:
            text = htmltext.flatten_inline(match.group(1))
            if text:
                return text
    match = TITLE_RE.search(markup)
    if match:
        text = htmltext.flatten_inline(match.group(1))
        text = re.sub(r"\s*\|\s*NDERF\s*$", "", text).strip(" |")
        if text:
            return text
    slug = re.sub(r"\.html?$", "", _slug(url))
    return slug.replace("_", " ").title()


def _parse_legacy(url, markup):
    start = LEGACY_START_RE.search(markup)
    end = LEGACY_END_RE.search(markup, start.end() if start else 0)
    segment = markup[
        start.end() if start else 0 : end.start() if end else len(markup)
    ]
    if not segment.strip():
        segment = markup

    stub = REDIRECT_STUB_RE.search(segment)
    if stub and len(htmltext.detag(segment)) < 400:
        return {"redirect": urljoin(url, stub.group(1))}

    # Section headers and question labels partition the page; anything between a
    # header and the next label is narrative.
    markers = []
    for kind, pattern in (("h", SECTION_MARKER_RE), ("q", QUESTION_MARKER_RE)):
        for match in pattern.finditer(segment):
            label = htmltext.flatten_inline(
                next((g for g in match.groups() if g is not None), "")
            )
            if label:
                markers.append((kind, label, match.start(), match.end()))
    markers.sort(key=lambda item: item[2])
    if not markers:
        return None

    narratives = []
    sections = []
    for position, (kind, label, _, marker_end) in enumerate(markers):
        stop = markers[position + 1][2] if position + 1 < len(markers) else len(segment)
        text = _clean(segment[marker_end:stop])
        if not text:
            continue
        if kind == "h":
            if htmltext.is_description_label(label) or DESC_HEADER_RE.match(label):
                narratives.append(text)
            elif text:
                sections.append((label, text))
        else:
            sections.append((label, text))

    if not narratives:
        # On a few pages the heading is wrapped so that the enclosing element
        # spans unrelated content, leaving no clean label to match. Fall back to
        # the bare phrase and read from there to the first question label.
        phrase = re.search(r"(?i)Experience\s+Descriptions?\b[^<]{0,60}", segment)
        if phrase:
            close = segment.find(">", phrase.end())
            cursor = close + 1 if -1 < close < phrase.end() + 40 else phrase.end()
            stop = next(
                (start for _, _, start, _ in markers if start > cursor), len(segment)
            )
            text = _clean(segment[cursor:stop])
            if text:
                narratives.append(text)

    if not narratives and not sections:
        return None
    return {
        "title": _title(markup, url),
        "body": "\n\n".join(narratives),
        "sections": sections,
    }


def _parse_modern(url, markup):
    start = MODERN_START_RE.search(markup)
    end = MODERN_END_RE.search(markup, start.end() if start else 0)
    if not start:
        return None
    segment = markup[start.end():end.start() if end else len(markup)]

    narratives = [_clean(m.group(1)) for m in EXP_DIV_RE.finditer(segment)]
    narratives = [n for n in narratives if n]
    sections = []
    for match in EXP_QA_RE.finditer(segment):
        label = htmltext.flatten_inline(match.group(1)).rstrip(": ")
        answer = _clean(match.group(2))
        if label and answer:
            sections.append((label, answer))

    if not narratives and not sections:
        return None  # soft-404: HTTP 200 with the shell but no content

    metadata = []
    for match in QUICK_FACT_RE.finditer(segment):
        label = htmltext.flatten_inline(match.group(1)).rstrip(": ")
        value = htmltext.flatten_inline(match.group(2))
        if label and value:
            metadata.append((label, value))
    greyson = GREYSON_RE.search(segment)
    if greyson:
        metadata.append(("Greyson Scale", greyson.group(1)))

    return {
        "title": _title(markup, url, EXP_TITLE_RE),
        "body": "\n\n".join(narratives),
        "sections": sections,
        "metadata": metadata,
    }


def parse(url, markup, doc=None):
    markup = htmltext.strip_premature_close(markup)
    markup = htmltext.strip_noise(markup)

    if MODERN_START_RE.search(markup):
        parsed = _parse_modern(url, markup)
    else:
        parsed = _parse_legacy(url, markup)
    if not parsed:
        return None
    if "redirect" in parsed:
        return parsed

    metadata = list(parsed.get("metadata") or [])
    if doc:
        for label, key in (
            ("Country", "COUNTRY_AI"), ("Age", "AGE"), ("Gender", "GENDER"),
        ):
            value = doc.get(key)
            if value and not any(existing == label for existing, _ in metadata):
                metadata.append((label, value))
        classification = doc.get("CLASSIFICATION")
        if classification:
            metadata.append(("Classification", ", ".join(classification)))
        if doc.get("EXCEPTIONAL"):
            metadata.append(("Exceptional", "yes"))
        for label, key in (("Condition", "Condition"), ("Editor's note", "Editorial")):
            if doc.get(key):
                metadata.append((label, doc[key]))

    return Story(
        site=SITE_KEY,
        story_id=_slug_key(url),
        title=parsed["title"],
        url=url,
        metadata=metadata,
        sections=parsed.get("sections") or [],
        body=parsed.get("body") or "",
    )
