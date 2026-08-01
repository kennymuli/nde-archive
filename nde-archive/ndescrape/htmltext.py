"""HTML -> plain text helpers.

Deliberately regex-based rather than DOM-based. These archives contain markup a
real parser handles *worse* than a naive one: oberf.org story pages emit a
spurious </body></html> about 4,500 bytes in while the real narrative continues
for another 40-80 KB, so every lenient DOM parser silently truncates the page and
loses the entire story. Slicing on markers sidesteps that whole class of bug.
"""

import html as html_module
import re

_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_DOWNLEVEL = re.compile(r"(?i)<!\[(?:if|endif)[^\]]*\]>")
_PREMATURE_CLOSE = re.compile(r"(?i)</\s*(?:body|html)\s*>")
_LINEBREAK_TAGS = re.compile(r"(?i)<br\b[^>]*>|</p\s*>|</div\s*>|</tr\s*>|</table\s*>|</li\s*>")
_ANY_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t\r\f\v]+")
_SPACED_NEWLINE = re.compile(r" *\n *")
_BLANK_RUN = re.compile(r"\n{3,}")


def strip_premature_close(markup):
    """Remove stray </body> / </html> that appear mid-document.

    Must run before any slicing on oberf.org pages.
    """
    return _PREMATURE_CLOSE.sub("", markup)


def strip_noise(markup):
    """Drop scripts, styles and MS-Word downlevel-revealed blocks.

    Deliberately leaves HTML comments in place: nderf.org marks its content
    region with <!--HERE--> and <!--footer-->, so stripping comments here would
    erase the slice boundaries and pull the page footer into the last answer.
    Comments are removed later, per fragment, by detag().
    """
    markup = _SCRIPT_STYLE.sub(" ", markup)
    markup = _DOWNLEVEL.sub(" ", markup)
    return markup


# Sequences that appear when UTF-8 bytes were decoded as cp1252 and the result
# was saved back as UTF-8. Some source pages ship already corrupted this way, so
# no amount of correct decoding on our side fixes them.
# The lead byte of a UTF-8 sequence read as cp1252 always lands on one of these,
# followed by run bytes that land in the C1/Latin-1 supplement or the cp1252
# punctuation block. \u0080-\u009f must be included: a decoder that passed the
# five cp1252-undefined bytes through leaves those code points in the run.
_MOJIBAKE_RUN = re.compile(
    "[\u00c3\u00c2\u00e2]"
    "[\u0080-\u00ff\u20ac\u201a\u0192\u201e\u2026\u2020\u2021\u02c6"
    "\u2030\u0160\u2039\u0152\u017d\u2018\u2019\u201c\u201d\u2022"
    "\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\u017e\u0178]+"
)


def _to_original_bytes(run):
    """Recover the bytes a mojibake run was mis-decoded from.

    cp1252 leaves five byte values undefined (0x80, 0x81, 0x8d, 0x9d, 0x9e). A
    decoder that passed those through leaves code points cp1252 cannot re-encode,
    so they fall back to latin-1, which maps U+0080-U+00FF onto the same bytes.
    """
    out = bytearray()
    for char in run:
        try:
            out.extend(char.encode("cp1252"))
        except UnicodeEncodeError:
            if ord(char) > 0xFF:
                raise
            out.extend(char.encode("latin-1"))
    return bytes(out)


def repair_mojibake(text):
    """Undo double-encoding, one run at a time.

    Repairing per matched run rather than re-decoding the whole string means a
    page that is only partly corrupted keeps its correct characters intact.
    """
    if not text or not _MOJIBAKE_RUN.search(text):
        return text

    def fix(match):
        run = match.group(0)
        try:
            return _to_original_bytes(run).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return run

    return _MOJIBAKE_RUN.sub(fix, text)


_NUMERIC_ENTITY = re.compile(r"&#(x[0-9a-fA-F]+|[0-9]+);")


def _resolve_numeric_entity(match):
    raw = match.group(1)
    try:
        code = int(raw[1:], 16) if raw[0] in "xX" else int(raw)
    except ValueError:
        return match.group(0)
    if 0 < code <= 0x10FFFF:
        return chr(code)
    return match.group(0)


# Tags that survive as literal text because the source escaped them (&lt;br&gt;),
# so they only become tag-shaped after unescaping.
_ESCAPED_BREAK = re.compile(r"(?i)&?<\s*br\s*/?\s*>|&?<\s*/\s*p\s*>")
_ESCAPED_TAG = re.compile(
    r"(?i)<\s*/?\s*(?:p|div|span|font|b|i|u|em|strong|br|table|tr|td|ul|ol|li|a|o:p)"
    r"(?:\s[^<>]{0,120})?/?\s*>"
)

# Site chrome that some pages carry inside the content region rather than in the
# page footer, so slicing alone does not remove it.
_CHROME = re.compile(
    r"(?im)^.*(?:©\s*\d{4}[-–]\d{4}\s*NDERF"
    r"|All Rights Reserved\."
    r"|Click here for more information\.).*$"
)


def detag(fragment):
    """Flatten an HTML fragment to text, preserving paragraph breaks.

    The tag-to-newline step has to happen before the blanket tag strip, otherwise
    <br>-separated paragraphs collapse into one run-on line.
    """
    if not fragment:
        return ""
    text = _SCRIPT_STYLE.sub(" ", fragment)
    text = _COMMENT.sub(" ", text)
    text = _LINEBREAK_TAGS.sub("\n", text)
    text = _ANY_TAG.sub("", text)
    text = html_module.unescape(text)
    # A few pages double-escape character references (&amp;#9786;), so one pass
    # leaves a literal "&#9786;". Resolve numeric refs only - re-running the full
    # unescape would also rewrite ampersands the author typed deliberately.
    text = _NUMERIC_ENTITY.sub(_resolve_numeric_entity, text)
    # Second pass: markup that was escaped in the source is only now tag-shaped.
    text = _ESCAPED_BREAK.sub("\n", text)
    text = _ESCAPED_TAG.sub("", text)
    text = repair_mojibake(text)
    text = _CHROME.sub("", text)
    return tidy(text)


def flatten_inline(fragment):
    """Flatten to a single line - for labels, titles and short values."""
    if not fragment:
        return ""
    text = _ANY_TAG.sub(" ", fragment)
    text = html_module.unescape(text)
    text = text.replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", text).strip()


def tidy(text):
    """Normalize whitespace without destroying real paragraph breaks."""
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("​", "").replace("﻿", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)
    text = _SPACED_NEWLINE.sub("\n", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


_WORD_WRAP = re.compile(r"(?<=[^\s.!?:;\"')\]])\n(?=[a-z0-9(\"'])")


def unwrap_hard_breaks(text):
    """Rejoin lines broken mid-sentence by the original MS-Word export.

    Much of this content was pasted from Word and hard-wrapped at ~75 columns, so
    single newlines inside a sentence are formatting noise rather than intent.
    Only joins when the break clearly falls mid-sentence: the previous line does
    not end in terminal punctuation and the next starts lowercase.
    """
    if not text:
        return ""
    parts = re.split(r"\n{2,}", text)
    return "\n\n".join(_WORD_WRAP.sub(" ", part) for part in parts)


def unescape(value):
    return html_module.unescape(value or "")


_DESC_PHRASE = re.compile(r"^experiencedescriptions?\b", re.I)


def is_description_label(text):
    """Does this label introduce the free-text narrative?

    Whitespace is removed before matching because the source frequently breaks
    the line mid-word ("Expe\\nrience description:"), and the heading is often
    qualified with an entry number, a date, or a provenance note
    ("Experience Description: Baidu/Tieba forum"). Requiring an exact match on
    the bare phrase silently drops all three shapes.
    """
    if not text:
        return False
    squashed = re.sub(r"[\s ]+", "", text)
    return bool(_DESC_PHRASE.match(squashed))
