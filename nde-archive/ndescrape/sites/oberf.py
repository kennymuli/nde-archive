"""oberf.org - Out of Body Experience Research Foundation.

A flat static site: every story lives at the document root. Discovery unions the
A-Z sitemap with all 20 category index pages, because each is independently
incomplete - the sitemap has a corrupted stretch through section D, and the
category pages miss older orphaned stories.
"""

import re
from urllib.parse import unquote, urljoin, urlparse

from .. import htmltext
from ..record import Story

SITE_KEY = "oberf"
SITE_TITLE = "OBERF - Out of Body Experience Research Foundation"
SITE_URL = "https://www.oberf.org/"
BASE = "https://www.oberf.org"

SEEDS = [
    "https://www.oberf.org/indexcontents.htm",
    "https://www.oberf.org/stories_obe.htm",
    "https://www.oberf.org/obethru2013.htm",
    "https://www.oberf.org/sobe_stories.htm",
    "https://www.oberf.org/sobe_stories1.htm",
    "https://www.oberf.org/sobe_stories2.htm",
    "https://www.oberf.org/sobe_stories3.htm",
    "https://www.oberf.org/ste.htm",
    "https://www.oberf.org/ste1999_2008.htm",
    "https://www.oberf.org/ste2009_2012.htm",
    "https://www.oberf.org/ste2013_2014.htm",
    "https://www.oberf.org/nde_like_stories.htm",
    "https://www.oberf.org/ndelikethru2011.htm",
    "https://www.oberf.org/other_stories.htm",
    "https://www.oberf.org/otherthru2013.htm",
    "https://www.oberf.org/prebirth.htm",
    "https://www.oberf.org/dbv.htm",
    "https://www.oberf.org/dream_stories.htm",
    "https://www.oberf.org/ufo.htm",
    "https://www.oberf.org/prayer.htm",
    "https://www.oberf.org/new_stories.html",
]

# Stories are identified by a personal-name + experience-type filename suffix.
# Index and editorial pages never take this shape. The optional digits after the
# underscore matter: a handful of slugs read _2sobe / _3obe when one person
# contributed several accounts, and omitting them drops real stories.
STORY_RE = re.compile(
    r"_\d*(sobeadcs|sobeufo|sobes|sobe|stes|ste|obeadc|obes|obe|mobes|mobe|nobe"
    r"|others|other|ndelike|ndes|nde|nda|nele|prebirth|dbv|prayer|dreams|dream"
    r"|meditations|meditation|med|wv|ld|premonitions|premonition|precognition"
    r"|prem|adcs|adc|orbs|pastlife|ufo|sde|sda|fde|deja|travel|vision|shared"
    r"|icu|feardeath)(?:\d+)?(?:_\d+[a-z]*)?(?:\(\d+\))?\.html?$",
    re.I,
)

# Editorial and index pages whose filenames happen to satisfy STORY_RE.
HARD_EXCLUDE = {
    "/obe_travel.htm",
    "/bright_night_vision.htm",
    "/how_to_obe.htm",
    "/uday_orbs.htm",
    "/stories_obe.htm",
    "/nde_like_stories.htm",
    "/dream_stories.htm",
    "/other_stories.htm",
    "/sobe_stories.htm",
}

# Broken apostrophe/space filenames that 404. Their content is reachable at
# working slugs already present in the set.
KNOWN_DEAD = {
    "/thomas_m's_obe.htm",
    "/Christopher's%20OBE.htm",
    "/Christopher%27s%20OBE.htm",
    "/Jena's%20OBE.htm",
    "/Jena%27s%20OBE.htm",
}

# Three real stories whose filenames carry no type suffix at all.
EXTRA_STORIES = ["/hannah_h.htm", "/sinead_o.htm", "/steven_s.htm"]

HREF_RE = re.compile(
    r"""<a\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I | re.S
)

CATEGORY_LABELS = [
    ("sobeadcs", "Shared OBE / ADC"), ("sobeufo", "Shared OBE / UFO"),
    ("sobes", "Shared OBE"), ("sobe", "Shared OBE"),
    ("obeadc", "OBE / After-Death Communication"),
    ("mobes", "Multiple OBE"), ("mobe", "Multiple OBE"),
    ("nobe", "Near-OBE"), ("obes", "Out of Body Experience"),
    ("obe", "Out of Body Experience"),
    ("stes", "Spiritually Transformative Experience"),
    ("ste", "Spiritually Transformative Experience"),
    ("ndelike", "NDE-like Experience"), ("nele", "Near-Death-Like Experience"),
    ("ndes", "Near Death Experience"), ("nde", "Near Death Experience"),
    ("nda", "Nearing Death Awareness"),
    ("prebirth", "Prebirth Experience"), ("dbv", "Deathbed Vision"),
    ("prayer", "Prayer Experience"),
    ("dreams", "Dream Experience"), ("dream", "Dream Experience"),
    ("meditations", "Meditation Experience"), ("meditation", "Meditation Experience"),
    ("med", "Meditation Experience"),
    ("wv", "Waking Vision"), ("ld", "Lucid Dream"),
    ("premonitions", "Premonition"), ("premonition", "Premonition"),
    ("precognition", "Precognition"), ("prem", "Premonition"),
    ("adcs", "After-Death Communication"), ("adc", "After-Death Communication"),
    ("orbs", "Orbs"), ("pastlife", "Past Life Experience"), ("ufo", "UFO Experience"),
    ("sde", "Shared Death Experience"), ("sda", "Shared Death Awareness"),
    ("fde", "Fear Death Experience"), ("deja", "Deja Vu"),
    ("travel", "OBE Travel"), ("vision", "Vision"), ("shared", "Shared Experience"),
    ("icu", "ICU Experience"), ("feardeath", "Fear-Death Experience"),
]

_SUFFIX_RE = re.compile(r"_([a-z]+?)(?:\d+)?(?:_\d+[a-z]*)?(?:\(\d+\))?\.html?$", re.I)


def category_for(path):
    match = _SUFFIX_RE.search(unquote(path))
    if not match:
        return None
    suffix = match.group(1).lower()
    for key, label in CATEGORY_LABELS:
        if suffix == key:
            return label
    return None


def normalize(href, base=BASE + "/"):
    href = (href or "").strip().replace("\r", "").replace("\n", "").replace("\t", "")
    if not href:
        return None
    low = href.lower()
    if low.startswith(("mailto:", "javascript:", "tel:")) or href.startswith("#"):
        return None
    parsed = urlparse(urljoin(base, href))
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "oberf.org":
        return None
    # An href resolving to the bare origin yields an empty path; guard against
    # emitting "https://www.oberf.org" + "" as a fetch target.
    return parsed.path if parsed.path and parsed.path != "/" else None


def extract_links(markup):
    paths = set()
    for match in HREF_RE.finditer(markup):
        href = match.group(1) or match.group(2) or match.group(3)
        path = normalize(href)
        if path:
            paths.add(path)
    return paths


def discover(fetch, log):
    """Union the sitemap and every category page; neither alone is complete."""
    paths = set()
    for seed in SEEDS:
        try:
            markup = fetch(seed)
        except Exception as exc:  # noqa: BLE001
            log("  ! seed failed %s (%s)" % (seed, exc))
            continue
        found = extract_links(markup)
        paths |= found
        log("  seed %-46s %5d links" % (seed.rsplit("/", 1)[-1], len(found)))

    stories = {p for p in paths if STORY_RE.search(unquote(p))}
    stories |= set(EXTRA_STORIES)
    stories -= HARD_EXCLUDE
    # Several category index pages (stories_obe.htm, dream_stories.htm, ...) also
    # satisfy STORY_RE; excluding every seed path removes them by construction
    # rather than relying on the blacklist staying in sync.
    stories -= {urlparse(seed).path for seed in SEEDS}
    stories = {p for p in stories if p not in KNOWN_DEAD and unquote(p) not in KNOWN_DEAD}

    urls = sorted(BASE + p for p in stories)
    log("  -> %d story URLs (%d raw same-site links)" % (len(urls), len(paths)))
    return urls


# -- extraction ------------------------------------------------------------

# Every editorial label and questionnaire prompt is painted green; the
# experiencer's own words are blue. That colour convention is the one reliable
# structural signal across ~25 years of template drift.
# Older Word-exported pages paint labels with <font COLOR="#008000"> instead of a
# green <span>; matching only the span form leaves the end boundary unfound and
# lets the whole questionnaire bleed into the narrative.
LABEL_RE = re.compile(
    r"<(?:span|font)\b[^>]*?"
    r"(?:class\s*=\s*[\"']?m108[\"']?|color\s*[:=]\s*[\"']?(?:green|\#008000))"
    r"[^>]*>(.*?)</(?:span|font)>",
    re.I | re.S,
)
DESCRIPTION_RE = re.compile(r"^\s*experience\s+description", re.I)
TITLE_RE = re.compile(
    r"<span\b[^>]*class\s*=\s*[\"']?(?:FirstTitle|m10[0-2])[\"']?[^>]*>(.*?)</span>",
    re.I | re.S,
)
HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_PUNCT_ONLY = re.compile(r"^[\s:;,.\-–—]*$")


def _labels(markup):
    """Green labels, with split-across-two-spans questions merged back together."""
    raw = []
    for match in LABEL_RE.finditer(markup):
        text = htmltext.flatten_inline(match.group(1))
        raw.append({"text": text, "start": match.start(), "end": match.end()})

    merged = []
    for item in raw:
        if not item["text"]:
            continue
        if merged:
            gap = markup[merged[-1]["end"]:item["start"]]
            if _PUNCT_ONLY.match(htmltext.flatten_inline(gap) or ""):
                # The site occasionally splits one prompt across two spans.
                merged[-1]["text"] = (merged[-1]["text"] + " " + item["text"]).strip()
                merged[-1]["end"] = item["end"]
                continue
        merged.append(dict(item))
    return merged


def _title(markup, url):
    for match in TITLE_RE.finditer(markup):
        text = htmltext.flatten_inline(match.group(1))
        if text and len(text) < 120:
            return text
    match = HTML_TITLE_RE.search(markup)
    if match:
        text = htmltext.flatten_inline(match.group(1))
        if text and text.lower() not in ("untitled document", "untitled"):
            return text
    slug = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return unquote(slug).replace("_", " ").title()


def parse(url, markup):
    markup = htmltext.strip_premature_close(markup)
    markup = htmltext.strip_noise(markup)

    labels = _labels(markup)
    if not labels:
        return None

    narratives = []
    sections = []
    for position, label in enumerate(labels):
        end = labels[position + 1]["start"] if position + 1 < len(labels) else len(markup)
        body = htmltext.detag(markup[label["end"]:end])
        if not body:
            continue
        body = htmltext.unwrap_hard_breaks(body)
        if DESCRIPTION_RE.match(label["text"]):
            narratives.append(body)
        else:
            sections.append((label["text"], body))

    if not narratives and not sections:
        return None
    # Some pages carry no "Experience description" heading at all - the account is
    # told entirely through questionnaire answers. Those answers are the story, so
    # keep the page rather than discarding a real narrative for lacking a header.

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
