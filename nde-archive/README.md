# NDE archive extractor

Extracts every published first-person account from the three sister sites of the
Near Death Experience Research Foundation and writes **one file per site**.

| Site | What it collects | Stories found |
|---|---|---|
| [nderf.org](https://www.nderf.org/) | Near-death experiences | ~5,800 |
| [adcrf.org](https://www.adcrf.org/) | After-death communications | ~1,800 |
| [oberf.org](https://www.oberf.org/) | Out-of-body & related experiences | ~2,290 |

> **Note on the domain names.** The request named `aderf.org` and `oderf.org`;
> neither resolves. The actual sister sites of nderf.org are **adcrf.org** (After
> Death Communication Research Foundation) and **oberf.org** (Out of Body
> Experience Research Foundation) — same foundation, same site engine. Those are
> what this tool reads.

## Usage

Python 3.7+ with **no third-party dependencies**. Nothing to install.

```bash
python3 scrape.py
```

That writes `output/nderf.md`, `output/adcrf.md` and `output/oberf.md`.

```bash
python3 scrape.py --format txt            # plain text instead of Markdown
python3 scrape.py --sites adcrf,oberf     # a subset of sites
python3 scrape.py --limit 25              # smoke test: 25 stories per site
python3 scrape.py --report                # also write per-site skip/failure logs
```

| Flag | Default | Meaning |
|---|---|---|
| `--sites` | `nderf,adcrf,oberf` | which sites to process |
| `--out` | `./output` | output directory |
| `--cache` | `./.cache` | page cache directory |
| `--format` | `md` | `md` or `txt` |
| `--limit` | none | cap stories per site |
| `--workers` | `2` | concurrent requests per site |
| `--delay` | `0.4` | minimum seconds between requests to one server |
| `--min-words` | `25` | discard entries shorter than this |
| `--report` | off | write skipped/failed URLs per site |

Every page is cached on disk, so **an interrupted run resumes without
re-downloading**. A full run takes roughly an hour cold and a couple of minutes
warm. Delete `.cache/` to force a fresh fetch.

## Output shape

Each file opens with a header (story count, word count, extraction date) and then
one section per story:

```markdown
## 41. Jane D NDE 1234

- **Experience type:** Near Death Experience
- **Country:** United States
- **Source:** https://www.nderf.org/Experiences/1jane_d_nde.html

<the narrative, paragraphs preserved>

### Did you feel separated from your body?
<the answer>
```

The questionnaire that accompanies each account is preserved as `###`
subsections, because on a significant number of pages the questionnaire answers
*are* the account — those pages have no free-text narrative at all.

## How it works

Three sites, three genuinely different architectures. The interesting part is
that the obvious approach is wrong on all three.

### nderf.org — the archive spine, not the search API

nderf.org has a JSON search API at `search.nderf.org/api/get`, which looks like
the clean way in. It isn't:

- It advertises `totalPages: 292` but returns **HTTP 500 for any page ≥ 49**,
  capping a single query at 980 of its 5,826 records.
- Its filter fields are **not covering partitions** — `GENDER=M` plus `GENDER=F`
  sums to 5,731, not 5,826; four of the documented `age` values return zero; and
  `CLASSIFICATION=NDE` reaches only 4,225. So no combination of queries can be
  shown to reach everything.
- Unknown query keys are treated as filter predicates on nonexistent fields, so a
  typo like `&limit=100` returns `resultCount: 0` rather than an error.

Instead, discovery walks the static `Archives/archivelist.htm` → 52 archive pages
→ **5,811 story URLs**, within 0.3% of the API's own total, from plain HTML with
no such traps. The API is still consulted, but only to enrich metadata (country,
age, classification, editor's notes).

### adcrf.org and oberf.org — union of two incomplete indexes

Both sites have an A–Z sitemap *and* a set of category/era index pages, and on
both sites **each is independently incomplete**:

- oberf.org's sitemap has a corrupted stretch through section D — 19 stories
  (`dolores_*`, `donna_*`, `dorothy_*`, …) appear only in the category pages,
  while 56 older orphaned stories appear only in the sitemap.
- adcrf.org's era archives hold 14 live stories the sitemap omits.

So discovery unions both and de-duplicates.

### Extraction: colour, not structure

These pages span roughly 25 years of hand-authored HTML across at least five
template vintages. There is no stable DOM structure to select on — but there *is*
a stable **colour convention**: editorial labels and questionnaire prompts are
painted green (`.m108`, `color:green`, `#008000`) or teal (`.m105`, `#009999`),
while the experiencer's own words are blue. Every extractor here partitions the
page on those label elements: text following an "Experience description" label is
narrative, text following any other label is a questionnaire answer.

## Things that will bite you if you rewrite this

Each of these cost a real debugging cycle and is guarded in the code:

- **Do not use an HTML parser on oberf.org.** Story pages emit a spurious
  `</body></html>` about 4,500 bytes in while the narrative continues for another
  40–80 KB. Every lenient DOM parser truncates there and silently returns *zero*
  narrative. `strip_premature_close()` removes those tags before any slicing.
- **Do not strip HTML comments before slicing.** nderf.org delimits its content
  region with `<!--HERE-->` and `<!--footer-->`. Removing comments first erases
  the boundaries and pulls the site footer into the last answer — which produced
  boilerplate in 45 of 45 sampled pages before it was caught.
- **Do not send `User-Agent: Mozilla/5.0`.** All four hosts run mod_security and
  answer that exact string with `406 Not Acceptable`. A descriptive UA (or none)
  works fine.
- **Do not strip a trailing `_NNNN` from nderf slugs when de-duplicating.** That
  number is what distinguishes different contributors who share a name — there
  are seven separate `john_b_nde` accounts. Collapsing it loses ~530 stories.
- **adcrf.org and oberf.org are the same physical server** (192.185.31.30), so
  they share one concurrency budget rather than getting one each.
- **Empty "spacer" label spans** sit directly under some headings. Treating one
  as a boundary yields an empty narrative and drops the story; labels whose
  content flattens to nothing are skipped.
- **Character encoding is unsignalled.** The hosts send `Content-Type: text/html`
  with no charset, so `requests`/`urllib` guess ISO-8859-1 and mojibake every
  curly quote. The content is UTF-8, sometimes with a BOM, sometimes not.

## Politeness

No host publishes a `robots.txt` (all four 404 it), which this treats as *no
directives published*, not as permission — so the defaults are conservative: 2
concurrent requests per server, ≥0.4 s between requests, exponential backoff with
jitter on 429/5xx, `Retry-After` honoured, and a descriptive User-Agent. The
on-disk cache means a re-run costs the sites nothing.

These are personal accounts published by their authors for public reading. The
extracted files are a personal-use research archive; each account remains the
work of its author, and the foundation retains its rights. Don't redistribute
them.

## Layout

```
scrape.py              CLI entry point
ndescrape/
  http.py              caching fetcher, rate limiter, retry/backoff, decoding
  htmltext.py          tolerant HTML -> text (regex, deliberately not a DOM parser)
  record.py            the Story record and the Markdown/text writers
  runner.py            orchestration: discover -> fetch -> extract -> write
  sites/
    nderf.py           archive-spine discovery + 3 legacy templates + modern template
    adcrf.py           sitemap ∪ era archives, colour-partition extraction
    oberf.py           sitemap ∪ 20 category pages, colour-partition extraction
```
