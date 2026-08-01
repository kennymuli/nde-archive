"""adcrf.org - After Death Communication Research Foundation.

Same hosting and template lineage as oberf.org, but discovery differs: the A-Z
sitemap and the per-era archive pages each hold stories the other omits, so both
are required. A post-fetch content gate rejects anything that turns out not to be
a story regardless of what its filename looked like.
"""

import re
from urllib.parse import unquote, urljoin, urlparse

from .. import htmltext
from ..record import Story

SITE_KEY = "adcrf"
SITE_TITLE = "ADCRF - After Death Communication Research Foundation"
SITE_URL = "https://www.adcrf.org/"
BASE = "https://www.adcrf.org"

SEEDS = [
    "https://www.adcrf.org/index.html",
    "https://www.adcrf.org/indexcontents.htm",
    "https://www.adcrf.org/new_stories.html",
    "https://www.adcrf.org/archived_2002.htm",
    "https://www.adcrf.org/archives_2003_2007.htm",
    "https://www.adcrf.org/archives_2008_2010.htm",
    "https://www.adcrf.org/archives_2011_2012.htm",
    "https://www.adcrf.org/archives_2013_2014.html",
    "https://www.adcrf.org/archives_2015_2016.html",
    "https://www.adcrf.org/archives_2017_2018.html",
]

# Index, navigation and editorial pages. Matched on basename, case-insensitively.
NON_STORY_RE = re.compile(
    r"^(?:index|indexcontents|new_stories|archived_\d+|archives_[\d_]+(?:\.htm)?"
    r"|articles|books|books_for_grieving|faq|privacy|weblinks|search"
    r"|adcrf_overview|adcrf_research|adc[ _]overview|adcrf[ _]research"
    r"|adc_reality|brief_overview_adc|houck_research|iands_2003|grief_rev_john"
    r"|terri_daniels)\.html?$",
    re.I,
)
GENERIC_INDEX_RE = re.compile(r"^(?:index|archive[sd]?)[a-z0-9_]*\.html?$", re.I)

# Broken filenames (stray apostrophes / spaces) that return a genuine 404. Each
# has a live twin already in the set.
KNOWN_DEAD = {
    "/Patrick S's ADCs.htm",
    "/kari_rh's.htm",
    "/r_d_adc's.htm",
}

HREF_RE = re.compile(
    r"""<a\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s">]+))""", re.I | re.S
)

_SUFFIX_RE = re.compile(r"_([a-z]+?)(?:\d+)?(?:_\d+[a-z]*)?\.html?$", re.I)

CATEGORY_LABELS = {
    "adc": "After-Death Communication",
    "adcs": "After-Death Communication",
    "dbv": "Deathbed Vision",
    "nele": "Near-Death-Like Experience",
    "nde": "Near Death Experience",
    "nda": "Nearing Death Awareness",
    "ste": "Spiritually Transformative Experience",
    "sobe": "Shared Out of Body Experience",
    "sobes": "Shared Out of Body Experience",
    "obe": "Out of Body Experience",
    "obes": "Out of Body Experience",
    "mobes": "Multiple Out of Body Experience",
    "dream": "Dream Experience",
    "ld": "Lucid Dream",
    "evp": "Electronic Voice Phenomenon",
    "other": "Other Experience",
    "sde": "Shared Death Experience",
    "prebirth": "Prebirth Experience",
}


def category_for(path):
    match = _SUFFIX_RE.search(unquote(path))
    if not match:
        return None
    return CATEGORY_LABELS.get(match.group(1).lower())


def normalize(href, base=BASE + "/"):
    href = (href or "").strip().replace("\r", "").replace("\n", "").replace("\t", "")
    if not href:
        return None
    low = href.lower()
    if low.startswith(("mailto:", "javascript:", "tel:")) or href.startswith("#"):
        return None
    href = href.split("#")[0]
    if not href:
        return None
    # Some hrefs contain literal spaces; encode before joining so urljoin does
    # not mangle them.
    href = href.replace(" ", "%20")
    parsed = urlparse(urljoin(base, href))
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "adcrf.org":
        return None
    path = parsed.path
    if not re.search(r"\.html?$", path, re.I):
        return None
    return path


def extract_links(markup):
    paths = set()
    for match in HREF_RE.finditer(markup):
        href = match.group(1) or match.group(2) or match.group(3)
        path = normalize(href)
        if path:
            paths.add(path)
    return paths


def is_story_path(path):
    decoded = unquote(path)
    if decoded.startswith("/French/"):
        return False
    if decoded in KNOWN_DEAD:
        return False
    basename = decoded.rsplit("/", 1)[-1]
    if NON_STORY_RE.match(basename) or GENERIC_INDEX_RE.match(basename):
        return False
    return True


def discover(fetch, log):
    paths = set()
    for seed in SEEDS:
        try:
            markup = fetch(seed)
        except Exception as exc:  # noqa: BLE001
            log("  ! seed failed %s (%s)" % (seed, exc))
            continue
        found = extract_links(markup)
        paths |= found
        log("  seed %-40s %5d links" % (seed.rsplit("/", 1)[-1], len(found)))

    stories = sorted(p for p in paths if is_story_path(p))
    urls = [BASE + p for p in stories]
    log("  -> %d story URLs (%d raw same-site links)" % (len(urls), len(paths)))
    return urls


# -- extraction ------------------------------------------------------------

START_RE = re.compile(r"(?i)Experience\s+Description\b[ \t\r\n]*(?:\d+)?[ \t\r\n]*:?")
# Questionnaire labels and section headers: either the modern m10x classes or the
# legacy inline colours. Narrative/answers are always blue; labels never are.
LABEL_OPEN_RE = re.compile(
    r"(?is)<(?:span|b|p|font|div)\b[^>]*"
    r"(?:class\s*=\s*[\"']?m10[24578][\"']?"
    r"|color\s*[:=]\s*[\"']?(?:green|purple|\#993366|\#009999)\b)"
    r"[^>]*>"  # consume the rest of the tag so .end() lands on real content
)
BACKGROUND_RE = re.compile(r"(?i)Background\s+Information")
TITLE_RE = re.compile(
    r"<(?:span|p|div|h1)\b[^>]*class\s*=\s*[\"']?FirstTitle[\"']?[^>]*>(.*?)</(?:span|p|div|h1)>",
    re.I | re.S,
)
HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
BODY_RE = re.compile(r"(?i)<body\b[^>]*>")

# A story page always carries the title style AND an "Experience description"
# heading. Editorial pages carry the former only.
GATE_TITLE_RE = re.compile(r"(?i)class\s*=\s*[\"']?FirstTitle")

# Backstop for pages where no label element follows the narrative.
QUESTION_LINE_RE = re.compile(
    r"(?im)^\s*(?:Did|Was|Were|Have|Has|How|What|Is there|Are there|Describe"
    r"|Please|Any |At the time|Following the experience|Degree of"
    r"|Length of time|Date of experience|General geographic)\b.*[?:]\s*$"
)


def _title(markup, url):
    match = TITLE_RE.search(markup)
    if match:
        text = htmltext.flatten_inline(match.group(1))
        if text and len(text) < 160:
            return text
    match = HTML_TITLE_RE.search(markup)
    if match:
        text = htmltext.flatten_inline(match.group(1))
        if text and text.lower() not in ("untitled document", "untitled"):
            return text
    slug = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return unquote(slug).replace("_", " ").title()


_SPACER = re.compile(r"^[\s:;,.\-–—]*$")


def _next_real_label(body, cursor):
    """First label element after `cursor` that actually carries text.

    The site emits contentless green spans purely as vertical spacing, often
    directly beneath the "Experience description" heading. Treating one of those
    as the end boundary yields an empty narrative and silently drops the story.
    """
    position = cursor
    while True:
        label = LABEL_OPEN_RE.search(body, position)
        if not label:
            return None
        close = body.find("</span>", label.end())
        if close == -1:
            close = min(len(body), label.end() + 400)
        if not _SPACER.match(htmltext.flatten_inline(body[label.end():close]) or ""):
            return label
        position = close + 1


def _segment_end(body, cursor):
    """Where the narrative that starts at `cursor` stops."""
    candidates = []
    label = _next_real_label(body, cursor)
    if label:
        candidates.append(label.start())
    background = BACKGROUND_RE.search(body, cursor)
    if background:
        candidates.append(background.start())

    if candidates:
        end = min(candidates)
        # Rewind to the opening '<' of the element we matched inside.
        opening = body.rfind("<", cursor, end)
        if opening != -1 and end - opening < 600:
            end = opening
        return end

    # No label followed: take the rest, then cut at the first line that reads
    # like a questionnaire prompt.
    tail = body[cursor:]
    flat = htmltext.detag(tail)
    question = QUESTION_LINE_RE.search(flat)
    if question:
        return cursor + len(tail)  # trimmed after detagging by the caller
    return len(body)


def _real_labels(body):
    """Every label element that carries text, in document order."""
    labels = []
    position = 0
    while True:
        match = LABEL_OPEN_RE.search(body, position)
        if not match:
            return labels
        close = body.find("</span>", match.end())
        if close == -1:
            close = min(len(body), match.end() + 400)
        text = htmltext.flatten_inline(body[match.end():close])
        if not _SPACER.match(text or ""):
            labels.append({"text": text, "start": match.start(), "end": close + len("</span>")})
        position = close + 1


def parse(url, markup):
    markup = htmltext.strip_premature_close(markup)
    markup = htmltext.strip_noise(markup)

    if not GATE_TITLE_RE.search(markup):
        return None

    body_match = BODY_RE.search(markup)
    body = markup[body_match.end():] if body_match else markup

    starts = list(START_RE.finditer(body))

    narratives = []
    for match in starts:
        cursor = match.end()
        # Step past the closing tag of the heading element itself.
        close = body.find("</span>", cursor, cursor + 80)
        if close != -1:
            cursor = close + len("</span>")
        end = _segment_end(body, cursor)
        text = htmltext.detag(body[cursor:end])
        if not text:
            continue
        question = QUESTION_LINE_RE.search(text)
        if question and question.start() > 0:
            text = text[:question.start()].rstrip()
        text = htmltext.unwrap_hard_breaks(text)
        if text:
            narratives.append(text)

    # The questionnaire that follows the narrative is part of the account, and on
    # some pages it is the whole of it - those have an "Experience description"
    # heading immediately followed by the first question and no prose at all.
    sections = []
    labels = _real_labels(body)
    for position, label in enumerate(labels):
        stop = labels[position + 1]["start"] if position + 1 < len(labels) else len(body)
        text = htmltext.detag(body[label["end"]:stop])
        if not text:
            continue
        text = htmltext.unwrap_hard_breaks(text)
        if htmltext.is_description_label(label["text"]):
            # Some pages break the heading mid-word or qualify it, so the raw
            # phrase match above finds nothing; recover the narrative from the
            # label instead of losing the story.
            if not narratives:
                narratives.append(text)
            continue
        sections.append((label["text"].rstrip(": "), text))

    if not narratives and not sections:
        return None

    path = urlparse(url).path
    metadata = []
    category = category_for(path)
    if category:
        metadata.append(("Experience type", category))

    return Story(
        site=SITE_KEY,
        story_id=unquote(path.lstrip("/")),
        title=_title(markup, url),
        url=url,
        metadata=metadata,
        sections=sections,
        body="\n\n".join(narratives),
    )
