"""The common story record and the Markdown/plain-text writers."""

import re

from .htmltext import repair_mojibake


def _clean_value(value):
    """Tidy a metadata value.

    Metadata arrives from the search API's JSON rather than from page HTML, so it
    never passes through detag() - which is where mojibake repair normally
    happens. Editor's notes carry translator credits ("Regine", "Rene") that are
    corrupted at the source, so they need the same treatment here.
    """
    return repair_mojibake(str(value).replace("\n", " ").strip())


class Story:
    """One experience account, normalized across all three sites."""

    __slots__ = ("site", "story_id", "title", "url", "metadata", "sections", "body")

    def __init__(self, site, story_id, title, url, metadata=None, sections=None, body=""):
        self.site = site
        self.story_id = story_id
        self.title = title or "(untitled)"
        self.url = url
        # Ordered list of (label, value) so output order is stable and meaningful.
        self.metadata = metadata or []
        # Ordered list of (heading, text) for questionnaire-style content.
        self.sections = sections or []
        self.body = body or ""

    @property
    def word_count(self):
        return len(self.body.split()) + sum(len(v.split()) for _, v in self.sections)

    def is_substantive(self, minimum_words=25):
        return self.word_count >= minimum_words


_HEADING_ESCAPE = re.compile(r"^(#{1,6})(\s)", re.M)


def _escape_markdown_block(text):
    """Keep story text from being reinterpreted as Markdown structure."""
    if not text:
        return ""
    return _HEADING_ESCAPE.sub(r"\\\1\2", text)


def render_markdown(story, index=None):
    lines = []
    heading = story.title
    if index is not None:
        heading = "%d. %s" % (index, story.title)
    lines.append("## %s" % heading)
    lines.append("")

    meta = list(story.metadata)
    meta.append(("Source", story.url))
    for label, value in meta:
        if value is None or value == "":
            continue
        value = _clean_value(value)
        if not value:
            continue
        lines.append("- **%s:** %s" % (label, value))
    lines.append("")

    if story.body.strip():
        lines.append(_escape_markdown_block(story.body.strip()))
        lines.append("")

    for label, value in story.sections:
        if not value or not value.strip():
            continue
        lines.append("### %s" % label.strip().rstrip(":"))
        lines.append("")
        lines.append(_escape_markdown_block(value.strip()))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_text(story, index=None):
    lines = []
    heading = story.title if index is None else "%d. %s" % (index, story.title)
    lines.append("=" * 78)
    lines.append(heading)
    lines.append("=" * 78)

    meta = list(story.metadata)
    meta.append(("Source", story.url))
    for label, value in meta:
        if value is None or value == "":
            continue
        value = _clean_value(value)
        if not value:
            continue
        lines.append("%s: %s" % (label, value))
    lines.append("")

    if story.body.strip():
        lines.append(story.body.strip())
        lines.append("")

    for label, value in story.sections:
        if not value or not value.strip():
            continue
        lines.append("-- %s --" % label.strip().rstrip(":"))
        lines.append(value.strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_collection(path, site_title, site_url, stories, fmt, generated_note):
    """Write every story for one site into a single file."""
    render = render_markdown if fmt == "md" else render_text
    total_words = sum(story.word_count for story in stories)

    with open(path, "w", encoding="utf-8") as handle:
        if fmt == "md":
            handle.write("# %s\n\n" % site_title)
            handle.write("- **Source site:** %s\n" % site_url)
            handle.write("- **Stories in this file:** %d\n" % len(stories))
            handle.write("- **Total words:** %s\n" % format(total_words, ","))
            handle.write("- **Extracted:** %s\n\n" % generated_note)
            handle.write(
                "> Personal-use archive of publicly published first-person accounts.\n"
                "> Each account remains the work of its author; the site owners retain\n"
                "> their rights. Not for redistribution.\n\n"
            )
            handle.write("---\n\n")
        else:
            handle.write("%s\n" % site_title)
            handle.write("Source site: %s\n" % site_url)
            handle.write("Stories in this file: %d\n" % len(stories))
            handle.write("Total words: %s\n" % format(total_words, ","))
            handle.write("Extracted: %s\n" % generated_note)
            handle.write(
                "\nPersonal-use archive of publicly published first-person accounts.\n"
                "Each account remains the work of its author. Not for redistribution.\n\n"
            )

        for position, story in enumerate(stories, 1):
            handle.write(render(story, position))
            handle.write("\n---\n\n" if fmt == "md" else "\n\n")

    return {"stories": len(stories), "words": total_words}
